import cmath
import sys

import numpy as np
import zenoh

sys.path.insert(0, "../src")

try:
    from zenoh_idl import sensor_msgs
except ImportError:
    print("Please run this script from inside /system_hw_test")

from matplotlib import pyplot as plot
from matplotlib.animation import FuncAnimation
from matplotlib.patches import Circle
from numpy import array, linspace
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks

"""
ros2 topic echo URID/pi/scan
ros2 topic echo URID/c3/battery_state
ros2 topic echo URID/c3/hazard_detection
"""

fig, ax = plot.subplots(2)

center = ax[0].plot([0], [0], "o", color="blue")[0]  # the robot
circle = ax[0].add_patch(Circle((0, 0), 0.16, color="red"))
line = ax[0].plot([], [], ".", color="black")[0]
front = ax[0].annotate("Front", xytext=(0.1, 0.3), xy=(0, 0.5))
arrow = ax[0].annotate("", xytext=(0, 0), xy=(0, 0.5), arrowprops=dict(arrowstyle="->"))
ax[0].set_xlim(-1, 1)
ax[0].set_ylim(-1, 1)
ax[0].set_aspect("equal")

line1 = ax[1].plot([], [], ".", color="red")[0]
line2 = ax[1].plot([], [], ".", color="green")[0]
ax[1].set_xlim(0, 680)
ax[1].set_ylim(-1, 51)  # cm

# Add captions to Fig2 to to orient people
gap = 5
ax[1].plot([0, 227 - gap], [50, 50], "-", color="red", linewidth=3.0)[0]
ax[1].plot([227 + gap, 453 - gap], [50, 50], "-", color="red", linewidth=3.0)[0]
ax[1].plot([453 + gap, 680], [50, 50], "-", color="red", linewidth=3.0)[0]
ax[1].annotate("Left", xytext=(100, 49), xy=(0, 0.5))
ax[1].annotate("Front", xytext=(320, 49), xy=(0, 0.5))
ax[1].annotate("Right", xytext=(550, 49), xy=(0, 0.5))
arrow_list = []

intensity_treshold = 1
# values from the sensor are either 0 or 47
# so any value bewtween 1 and 47 works

vectorM2 = np.zeros(1080)
vectorM1 = np.zeros(1080)

URID = "OM742d35Cc6634"

print(
    f"\n\n***********************\n***********************\nUsing {URID} as the URID - please make sure this is correct\none for your robot otherwise this script will not receive any data.\n***********************\n***********************\n"
)


def listenerScan(sample):
    # print(f"Received {sample.kind} ('{sample.key_expr}': '{sample.payload}')")
    scan = sensor_msgs.LaserScan.deserialize(sample.payload.to_bytes())
    # print(f"Scan {scan}")

    # ROS2 convention rotation
    # angles = list(map(lambda x: x*1j+cmath.pi/2j, np.arange(scan.angle_min, scan.angle_max, scan.angle_increment)))

    # this creates a list of angles
    # the point of the cmath.pi*1j is to rotate the data so that angles run from 0 to 2Pi (aka 6.28) rather than +/- Pi
    # in the plot, the FRONT of the robot is facing up
    angles = list(
        map(
            lambda x: x * 1j - cmath.pi / 1j,
            np.arange(scan.angle_min, scan.angle_max, scan.angle_increment),
        )
    )
    # angle_min=-3.1241390705108643, angle_max=3.1415927410125732

    complexes = []
    clusters = []

    # smoothing
    global vectorM1, vectorM2
    # Add the new data, with the last two data vectros
    # then divide by 3 -> simple averaging
    smv = np.add(scan.ranges, vectorM1)
    smv = np.add(smv, vectorM2)
    smv = np.divide(smv, 3)
    vectorM2 = vectorM1
    vectorM1 = scan.ranges

    for angle, distance, intensity in list(zip(angles, smv, scan.intensities)):
        # print("distance (m):", distance)
        # print("intensity:", intensity)
        # print("angle:", angle)
        # let's look only at close things (< 0.95m)
        if distance <= 0.50:
            if intensity >= intensity_treshold:
                complexes.append(distance * cmath.exp(angle))
                # convert to cm and flip to emphasize near returns
                clusters.append(51 - int(distance * 100))
            else:
                complexes.append(1024 * cmath.exp(angle))
                clusters.append(0)
        else:
            clusters.append(0)

    X = [i.real for i in complexes]
    Y = [i.imag for i in complexes]
    # # XY = [[i.real, i.imag] for i in complexes]

    # plot the raw data
    global line
    line.set_data(X, Y)

    a = array(clusters)
    # roll the data so the "nose" of the robot is in the middle (around 530)
    a = np.roll(a, 278)
    # flip so we are in the human/robot frame
    a = a[::-1]
    # smooth a bit
    x_kde = gaussian_filter1d(a, 5)

    # debug
    # print("raw data:", a)
    # print("x_kde:", x_kde)
    # print("length:", len(a))

    x_kde = x_kde[200:880]  # chop off data from the back of the robot
    # the full data run from 0 to 1079 (aka length 1080)
    s = linspace(0, len(x_kde), num=len(x_kde))

    # for debug
    line1.set_data(s, a[200:880])
    line2.set_data(s, x_kde)

    peaks, _ = find_peaks(x_kde, height=0)
    # print("peaks:", peaks)

    global arrow_list
    # clear the old arrows
    for arrow in arrow_list:
        arrow.remove()
    # arrow_list[:] = []
    arrow_list = []

    # add new arrows
    max_x_peak = -10  # arbitrary negative number
    max_y_peak = -10
    for x in peaks:
        y = x_kde[int(x)]
        if y > max_y_peak:
            max_y_peak = y
            max_x_peak = int(x)
        arrow = ax[1].annotate(
            "", xytext=(x, y + 3), xy=(x, y + 20), arrowprops=dict(arrowstyle="<-")
        )
        arrow_list.append(arrow)

    # # the closest object
    # arrow = ax[1].annotate("",
    #     xytext=(max_x_peak, max_y_peak), xy=(max_x_peak, max_y_peak + 10),
    #     arrowprops=dict(color='blue', lw=4, arrowstyle="<-"))
    # arrow_list.append(arrow)
    # print("closest_object:", max_x_peak)

    # the array has length 680
    proximity = "close to"
    direction = "on your left"
    if max_x_peak > 0:
        if max_y_peak > 80:
            proximity = "hitting"
        if max_x_peak > 453:
            direction = "on your right"
        elif max_x_peak > 227:
            direction = "in front of you"
        print(f"Warning, you are {proximity} something {direction}.")


def listenerBattery(sample):
    # print(f"Received {sample.kind} ('{sample.key_expr}': '{sample.payload}')")
    battery = sensor_msgs.BatteryState.deserialize(sample.payload.to_bytes())
    battery_percent = int(battery.percentage * 100)
    print(f"Battery Percentage {battery_percent}")
    if battery_percent < 5:
        print(
            "CRITICAL: your battery is almost empty. Immediately move to your charging station and recharge."
        )
    elif battery_percent < 15:
        print(
            "Caution: your battery is running low. Consider finding your charging stating and recharging."
        )


def listenerHazard(sample):
    # print(f"Received {sample.kind} ('{sample.key_expr}': '{sample.payload}')")
    hazard = sensor_msgs.HazardDetectionVector.deserialize(sample.payload.to_bytes())
    # print(f"Hazard {hazard}")
    if hazard.detections and len(hazard.detections) > 0:
        # print(f"Hazard Detections {hazard.detections}")
        for haz in hazard.detections:
            # print(f"Hazard Type:{haz.type} direction:{haz.header.frame_id}")
            if haz.type == 1:
                if haz.header.frame_id == "bump_front_right":
                    print("DANGER: you are hitting something on your front right.")
                elif haz.header.frame_id == "bump_front_left":
                    print("DANGER: you are hitting something on your front left.")
                elif haz.header.frame_id == "bump_front_center":
                    print("DANGER: you are hitting something right in front of you.")


print("[INFO] Opening zenoh session...")
conf = zenoh.Config()
z = zenoh.open(conf)

print("[INFO] Creating Subscribers")
scans = z.declare_subscriber(f"{URID}/pi/scan", listenerScan)
batts = z.declare_subscriber(f"{URID}/c3/battery_state", listenerBattery)
bump = z.declare_subscriber(f"{URID}/c3/hazard_detection", listenerHazard)

ani = FuncAnimation(fig, lambda _: None)
plot.show()
