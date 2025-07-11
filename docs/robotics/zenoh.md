# OM1

## Install Zenoh Middleware

[Zenoh](https://zenoh.io) is a pub/sub/query protocol unifying data in motion, data at rest and computations. You need two pieces - the `eclipse-zenoh` python libary and the Zenoh daemon (`zenohd`). Your Python project needs `eclipse-zenoh`, which is already added to OM1's `pyproject.toml`. 

### Mac

Install the Zenoh router:

```bash
$ brew tap eclipse-zenoh/homebrew-zenoh
$ brew install zenoh
```

### Linux

Install the Zenoh router:

```bash
$ echo "deb [trusted=yes] https://download.eclipse.org/zenoh/debian-repo/ /" | sudo tee -a /etc/apt/sources.list > /dev/null
$ sudo apt update
$ sudo apt install zenoh 
```

## Starting/testing the router

In a separate terminal window, start the router:

```bash
# inside OM1
zenohd -c robot_storage.json5
```

Testing:

```bash
zenohd --help
```

## Installing the persistent backend

See https://github.com/eclipse-zenoh/zenoh-backend-filesystem?tab=readme-ov-file#how-to-install-it

On Mac, you will need to allow `libzenoh_backend_fs.dylib` to run via `Privacy and Security`. Just try to run it separately - e.g. via the terminal, and then `approve` the various popup messages. Once you have tried to run this once, it will be cached and then `zenoh` can find the library the next time. 

The database is where-ever you set the path too

```bash
export ZENOH_BACKEND_FS_ROOT=$PWD/zenohdb/
```

## Using the REST API at ::9500

Using `curl` to publish and query keys/values, you can:

```bash
# Put values that will be stored under ${ZENOH_BACKEND_FS_ROOT}/robot
curl -X PUT -d "HELLO WORLD" http://localhost:9500/robot   

# Retrieve the values
curl http://localhost:9500/robot 
```
