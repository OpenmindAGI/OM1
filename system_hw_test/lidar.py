import struct

import matplotlib.cm as cmx
import matplotlib.colors
import matplotlib.pyplot as plt
import numpy as np

# fields=[
#       PointField_(name='x', offset=0, datatype=7, count=1),
#       PointField_(name='y', offset=4, datatype=7, count=1),
#       PointField_(name='z', offset=8, datatype=7, count=1),
#       PointField_(name='intensity', offset=16, datatype=7, count=1),
#       PointField_(name='ring', offset=20, datatype=4, count=1),
#       PointField_(name='time', offset=24, datatype=7, count=1)
# ]

data = np.loadtxt("lidar_raw.txt", delimiter=",")
data = data.astype(np.uint8)

print(f"Data size: {data.size}")
print(f"Data type: {data.dtype}")

sliced = bytes(data)
float_array2 = np.array(
    struct.unpack("11496f", sliced)
)  # '>4f' means big-endian, 4 floats
arr = float_array2.reshape((1437, 8))
print(arr[0])

x = arr[:, 0]
y = arr[:, 1]
z = arr[:, 2]

norm = matplotlib.colors.Normalize(vmin=min(z), vmax=max(z))
cmap = cmx.ScalarMappable(norm=norm, cmap=cmx.jet)
colors = cmap.to_rgba(z)

# Create the 3D plot
fig = plt.figure()
ax = fig.add_subplot(111, projection="3d")

# Scatter plot with colors based on z-values
scatter = ax.scatter(x, y, z, c=colors, marker="o")

# Add a color bar to show the z-value mapping
fig.colorbar(cmap, ax=ax)

# Set labels for axes
ax.set_xlabel("X")
ax.set_ylabel("Y")
ax.set_zlabel("Z")

# Display the plot
plt.title("3D Scatter Plot Colored by Z-value")
plt.show()
