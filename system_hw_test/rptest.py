import argparse
import math
import sys
import threading
import time

import bezier
import numpy as np
import zenoh
from matplotlib import pyplot as plot
from matplotlib.animation import FuncAnimation
from matplotlib.patches import Circle, Rectangle
from rpdriver import RPDriver

sys.path.insert(0, "../src")

try:
    from zenoh_idl import sensor_msgs
except ImportError:
    print("Please run this script from inside /system_hw_test")

parser = argparse.ArgumentParser()
parser.add_argument(
    "--serial", help="serial port to use, when using the low level driver", type=str
)
parser.add_argument("--URID", help="your robot's URID, when using Zenoh", type=str)
print(parser.format_help())

args = parser.parse_args()

"""
precompute Bezier trajectories
"""
curves = [
    bezier.Curve(np.asfortranarray([[0.0, -0.3, -0.75], [0.0, 0.5, 0.40]]), degree=2),
    bezier.Curve(np.asfortranarray([[0.0, -0.3, -0.70], [0.0, 0.6, 0.70]]), degree=2),
    bezier.Curve(np.asfortranarray([[0.0, -0.2, -0.60], [0.0, 0.7, 0.90]]), degree=2),
    bezier.Curve(np.asfortranarray([[0.0, -0.1, -0.35], [0.0, 0.7, 1.03]]), degree=2),
    bezier.Curve(np.asfortranarray([[0.0, 0.0, 0.00], [0.0, +0.5, +1.05]]), degree=2),
    bezier.Curve(np.asfortranarray([[0.0, +0.1, +0.35], [0.0, 0.7, 1.03]]), degree=2),
    bezier.Curve(np.asfortranarray([[0.0, +0.2, +0.60], [0.0, 0.7, 0.90]]), degree=2),
    bezier.Curve(np.asfortranarray([[0.0, +0.3, +0.70], [0.0, 0.6, 0.70]]), degree=2),
    bezier.Curve(np.asfortranarray([[0.0, +0.3, +0.75], [0.0, 0.5, 0.40]]), degree=2),
    bezier.Curve(np.asfortranarray([[0.0, 0.0, 0.00], [0.0, -0.5, -1.05]]), degree=2),
]

paths = []
pp = []
s_vals = np.linspace(0.0, 1.0, 10)

for curve in curves:
    cp = curve.evaluate_multi(s_vals)
    paths.append(cp)
    pairs = list(zip(cp[0], cp[1]))
    pp.append(pairs)

print(paths)
print(pp)

fig = plot.figure()
ax1 = plot.subplot(131)
ax2 = plot.subplot(132)
ax3 = plot.subplot(133)

center = ax1.plot([0], [0], "o", color="blue")[0]  # the robot
circle = ax1.add_patch(Circle((0, 0), 0.20, color="red"))  # the robot
points = ax1.plot([], [], "-", color="black")[0]
front = ax1.annotate("Front", xytext=(0.1, 0.3), xy=(0, 0.5))
arrow = ax1.annotate("", xytext=(0, 0), xy=(0, 1.5), arrowprops=dict(arrowstyle="->"))
ax1.set_xlim(-5, 5)
ax1.set_ylim(-5, 5)
ax1.set_aspect("equal")

"""
Robot and sensor configuration
UNITREE
"""

half_width_robot = 0.20  # the width of the robot is 40 cm
max_relevant_distance = 1.1  # meters
sensor_mounting_angle = 172.0  # corrects for how sensor is mounted
angles_blanked = [[-180.0, -160.0], [160.0, 180.0]]

# Figure 2 - the zoom and the possible paths
centerZoom = ax2.plot([0], [0], "o", color="blue")[0]  # the robot

if args.URID:
    sensor_mounting_angle = 270.0
    angles_blanked = [[-180.0, -160.0], [110.0, 180.0]]
    circleZoom = ax2.add_patch(
        Circle((0, 0), 0.20, ls="--", lw=1, ec="red", fc="none")
    )  # the robot head
    outline = ax2.add_patch(
        Rectangle((-0.05, -0.15), 0.20, 0.06, ls="--", fc="black")
    )  # the robot electronics
else:
    circleZoom = ax2.add_patch(
        Circle((0, 0), 0.20, ls="--", lw=1, ec="red", fc="none")
    )  # the robot head
    outline = ax2.add_patch(
        Rectangle((-0.2, -0.7), 0.40, 0.70, ls="--", lw=1, ec="red", fc="none")
    )  # the robot body
pointsZoom = ax2.plot([], [], ".", color="black")[0]
ax2.set_xlim(-1.2, 1.2)
ax2.set_ylim(-1.2, 1.2)
ax2.set_aspect("equal")

lines = []
for li in list(range(0, len(curves) + 1)):
    lines.append(ax2.plot([0], [0], "-", color="black")[0])

line = ax3.plot([0], [0], "-", color="red")[0]
ax3.set_xlim(-180, 180)
ax3.set_ylim(0, 1.2)
ax3.set_aspect(300)

ax3.plot([-180.0, -48.0], [1.18, 1.18], "-", color="red", linewidth=3.0)[0]
ax3.plot([-42.0, 42.0], [1.18, 1.18], "-", color="black", linewidth=3.0)[0]
ax3.plot([48.0, 180.0], [1.18, 1.18], "-", color="green", linewidth=3.0)[0]
ax3.annotate("Left", xytext=(-125, 1.1), xy=(0, 0.5))
ax3.annotate("Front", xytext=(-20, 1.1), xy=(0, 0.5))
ax3.annotate("Right", xytext=(85, 1.1), xy=(0, 0.5))


# display the blanked regions of the scan
for b in angles_blanked:
    deg_to_rad = np.pi / 180.0

    start_angle = b[0] * deg_to_rad
    end_angle = b[1] * deg_to_rad

    theta = np.linspace(start_angle, end_angle, 50)
    r = max_relevant_distance

    x = r * np.sin(theta)
    y = r * np.cos(theta)

    # the arc
    ax2.plot(x, y, "--", color="grey", linewidth=1.5)

    # the straight lines
    ax2.plot([0, x[0]], [0, y[0]], "--", color="grey", linewidth=1)
    ax2.plot([0, x[-1]], [0, y[-1]], "--", color="grey", linewidth=1)

    # for panel 3 - this is in the correct units
    width = abs(b[1] - b[0])
    ax3.add_patch(Rectangle((b[0], 0.2), width, 1.0, fc="grey"))


def continuous_serial(lidar):

    for i, scan in enumerate(
        lidar.iter_scans(scan_type="express", max_buf_meas=3000, min_len=5)
    ):

        array = np.array(scan)

        # the driver sends angles in degrees between from 0 to 360
        # warning - the driver may send two or more readings per angle,
        # this can be confusing for the code
        angles = array[:, 1]

        # distances are in millimeters
        distances_mm = array[:, 2]
        distances_m = [i / 1000 for i in distances_mm]

        data = list(zip(angles, distances_m))
        array_ready = np.array(data)
        # print(f"Array {array_ready}")
        process(array_ready)


def zenoh_scan(sample):

    scan = sensor_msgs.LaserScan.deserialize(sample.payload.to_bytes())
    # print(f"Scan {scan}")

    # angle_min=-3.1241390705108643, angle_max=3.1415927410125732
    angles = list(
        map(
            lambda x: 360.0 * (x + math.pi) / (2 * math.pi),
            np.arange(scan.angle_min, scan.angle_max, scan.angle_increment),
        )
    )

    angles_final = np.flip(angles)
    # angles now run from 360.0 to 0 degress
    data = list(zip(angles_final, scan.ranges))
    array_ready = np.array(data)
    # print(f"Array {array_ready}")
    process(array_ready)


def process(data):

    complexes = []

    for angle, distance in data:

        d_m = distance

        # don't worry about distant objects
        if d_m > 5.0:
            continue

        # first, correctly orient the sensor zero to the robot zero
        angle = angle + sensor_mounting_angle
        if angle >= 360.0:
            angle = angle - 360.0
        elif angle < 0.0:
            angle = 360.0 + angle

        # then, convert to radians
        a_rad = angle * math.pi / 180.0

        v1 = d_m * math.cos(a_rad)
        v2 = d_m * math.sin(a_rad)

        # convert to x and y
        # x runs backwards to forwards, y runs left to right
        x = -1 * v2
        y = -1 * v1

        # convert the angle to -180 to + 180 range
        angle = angle - 180.0

        keep = True
        for b in angles_blanked:
            if angle >= b[0] and angle <= b[1]:
                # this is a permanent reflection based on the robot
                # disregard
                keep = False
                break

        # the final data ready to use for path planning
        if keep:
            complexes.append([x, y, angle, d_m])

    array = np.array(complexes)

    # sort data into strictly increasing angles to deal with sensor issues
    # the sensor sometimes reports part of the previous scan and part of the next scan
    # so you end up with multiple slightly different values for some angles at the
    # junction
    sorted_indices = array[:, 2].argsort()
    array = array[sorted_indices]

    X = array[:, 0]
    Y = array[:, 1]
    A = array[:, 2]
    D = array[:, 3]

    global points
    points.set_data(X, Y)

    global pointsZoom
    pointsZoom.set_data(X, Y)

    global line
    line.set_data(A, D)

    """
    Determine set of possible paths
    """
    possible_paths = np.array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
    bad_paths = []

    # all the possible conflicting points
    for x, y, d in list(zip(X, Y, D)):
        if d > max_relevant_distance:  # too far away - we do not care
            continue
        for apath in possible_paths:
            for point in pp[apath]:
                p1 = x - point[0]
                p2 = y - point[1]
                dist = math.sqrt(p1 * p1 + p2 * p2)
                if dist < half_width_robot:
                    # too close - this path will not work
                    path_to_remove = np.array([apath])
                    bad_paths.append(apath)
                    possible_paths = np.setdiff1d(possible_paths, path_to_remove)
                    break  # no need to keep checking this path - we know this path is bad

    print(f"possible_paths RP Lidar: {possible_paths}")

    # convert to simple list
    ppl = possible_paths.tolist()

    turn_left = []
    advance = []
    turn_right = []
    retreat = []

    for p in ppl:
        # all the possible paths
        if p < 4:
            turn_left.append(p)
        elif p == 4:
            advance.append(p)
        elif p < 9:
            turn_right.append(p)
        elif p == 9:
            retreat.append(p)
        lines[p].set_data(paths[p][0], paths[p][1])
        lines[p].set_color("green")

    if len(ppl) > 0:
        print(f"There are {len(ppl)} possible paths.")
        if len(turn_left) > 0:
            print(f"You can turn left using paths: {turn_left}.")
        if len(advance) > 0:
            print("You can advance.")
        if len(turn_right) > 0:
            print(f"You can turn right using paths: {turn_right}.")
        if len(retreat) > 0:
            print("You can retreat.")
    else:
        print(
            "You are surrounded by objects and cannot safely move in any direction. DO NOT MOVE."
        )

    for p in bad_paths:
        # these are all the bad paths
        lines[p].set_data(paths[p][0], paths[p][1])
        lines[p].set_color("red")


if __name__ == "__main__":

    if args.serial:
        PORT_NAME = args.serial
        print(f"Using {PORT_NAME} as the serial port")
        try:
            lidar = RPDriver(PORT_NAME)
            info = lidar.get_info()
            print(f"Info: {info}")

            health = lidar.get_health()
            print(f"Health: {health}")

            # reset to clear buffers
            lidar.reset()

            subscribe_thread = threading.Thread(target=continuous_serial, args=(lidar,))
            subscribe_thread.daemon = True
            subscribe_thread.start()

            ani = FuncAnimation(fig, lambda _: None)
            plot.show()

        except KeyboardInterrupt:
            print("Program interrupted")

        finally:
            print("Exiting program")
            lidar.stop()
            lidar.disconnect()
            time.sleep(0.5)
            sys.exit(0)
    elif args.URID:
        URID = args.URID
        print(f"Using Zenoh to connect to robot using {URID}")
        print("[INFO] Opening zenoh session...")
        conf = zenoh.Config()
        z = zenoh.open(conf)

        print("[INFO] Creating Subscribers")
        scans = z.declare_subscriber(f"{URID}/pi/scan", zenoh_scan)

        ani = FuncAnimation(fig, lambda _: None)
        plot.show()
    else:
        print("No sensor")
