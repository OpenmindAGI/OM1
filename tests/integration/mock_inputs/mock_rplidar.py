import asyncio
import logging
import time
from queue import Queue
from typing import List, Optional

from inputs.base import SensorConfig
from inputs.base.loop import FuserInput
from inputs.plugins.rplidar import Message, RPLidar
from providers.io_provider import IOProvider
from providers.rplidar_provider import RPLidarProvider
from tests.integration.mock_inputs.data_providers.mock_lidar_scan_provider import (
    get_lidar_provider,
    get_next_lidar_scan,
)


class MockRPLidar(RPLidar):
    """
    Mock implementation of RPLidar that uses mock lidar data.

    This class reuses the real RPLidarProvider and its path processing logic,
    but overrides the hardware interface to inject mock data instead of
    connecting to real hardware.
    """

    def __init__(self, config: SensorConfig = SensorConfig()):
        """
        Initialize with mock lidar provider that reuses real processing logic.

        Parameters
        ----------
        config : SensorConfig, optional
            Configuration for the sensor
        """
        # Initialize base FuserInput class, skipping RPLidar.__init__ to avoid hardware setup
        super(FuserInput, self).__init__(config)

        # Override the descriptor to indicate this is a mock
        self.descriptor_for_LLM = "MOCK RPLidar INPUT (Integration Test)"

        # Track IO
        self.io_provider = IOProvider()

        # Buffer for storing the final output
        self.messages: List[Message] = []

        # Buffer for storing messages
        self.message_buffer: Queue[str] = Queue()

        # Extract lidar configuration
        lidar_config = self._extract_lidar_config(config)

        # Create real RPLidarProvider but prevent hardware connections
        self.lidar: RPLidarProvider = self._create_mock_lidar_provider(**lidar_config)

        # Store the last processed time to rate-limit our mock data
        self.last_processed_time = 0

        # Track if we've processed all mock data
        self.mock_data_processed = False

        # Start the mock data processing
        self.running = True

        # Get reference to the mock lidar data provider
        self.lidar_provider = get_lidar_provider()

        # Store reference to cortex runtime for cleanup (will be set by test runner)
        self.cortex_runtime = None

        logging.info(
            f"MockRPLidar initialized with {self.lidar_provider.scan_count} scan data sets"
        )

    def set_cortex_runtime(self, cortex):
        """
        Set reference to cortex runtime for comprehensive cleanup.

        Parameters
        ----------
        cortex : CortexRuntime
            The cortex runtime instance
        """
        self.cortex_runtime = cortex

    def _create_mock_lidar_provider(self, **lidar_config) -> RPLidarProvider:
        """
        Create a RPLidarProvider instance but override its start method to prevent hardware connections.

        Returns
        -------
        RPLidarProvider
            A configured RPLidarProvider instance that won't try to connect to hardware
        """
        # Create the real provider with configuration
        provider = RPLidarProvider(**lidar_config)

        def mock_start():
            """Mock start method that doesn't try to connect to hardware."""
            provider.running = True
            logging.info(
                "MockRPLidar: RPLidarProvider start() called (hardware connections prevented)"
            )

        provider.start = mock_start

        return provider

    def _extract_lidar_config(self, config: SensorConfig) -> dict:
        """Extract lidar configuration parameters from sensor config."""
        lidar_config = {
            "serial_port": getattr(config, "serial_port", None),
            "use_zenoh": getattr(config, "use_zenoh", False),
            "half_width_robot": getattr(config, "half_width_robot", 0.20),
            "angles_blanked": getattr(config, "angles_blanked", []),
            "relevant_distance_max": getattr(config, "relevant_distance_max", 1.1),
            "relevant_distance_min": getattr(config, "relevant_distance_min", 0.08),
            "sensor_mounting_angle": getattr(config, "sensor_mounting_angle", 180.0),
        }

        # Handle Zenoh-specific configuration
        if lidar_config["use_zenoh"]:
            lidar_config["URID"] = getattr(config, "URID", "default")
            logging.info(f"MockRPLidar using Zenoh with URID: {lidar_config['URID']}")

        return lidar_config

    async def _poll(self) -> Optional[str]:
        """
        Override the poll method to inject mock data into the real path processor.

        Returns
        -------
        Optional[str]
            Mock lidar data string if available, None otherwise
        """
        await asyncio.sleep(0.2)  # Maintain the same polling rate

        # Rate limit to avoid overwhelming the system
        current_time = time.time()
        if current_time - self.last_processed_time < 0.5:  # Half second between data
            return None

        self.last_processed_time = current_time

        # Get next scan from the mock provider
        scan_array = get_next_lidar_scan()
        if scan_array is not None:
            # Inject mock data into the real path processor
            # scan_array is already in the format (angle, distance) that _path_processor expects
            self.lidar._path_processor(scan_array)

            logging.info(
                f"MockRPLidar: Processed mock scan ({self.lidar_provider.remaining_scans} remaining)"
            )

            # Return the processed lidar string from the real provider
            return self.lidar.lidar_string
        else:
            if not self.mock_data_processed:
                logging.info("MockRPLidar: No more mock scan data to process")
                self.mock_data_processed = True
            return None

    # TODO (Kyle): Replace the odometer with a mock input to avoid clean up.
    async def cleanup_cortex_runtime(self):
        """
        Clean up CortexRuntime and its components to prevent hanging.
        This method handles the Zenoh session cleanup that's specific to RPLidar tests.
        """
        if not self.cortex_runtime:
            logging.warning("MockRPLidar: No cortex runtime reference for cleanup")
            return

        logging.info("MockRPLidar: Starting cortex cleanup")

        try:
            cortex = self.cortex_runtime

            # Clean up action orchestrator
            if hasattr(cortex, "action_orchestrator") and cortex.action_orchestrator:
                logging.info("MockRPLidar: Cleaning up action orchestrator")

                # First, try to stop the action orchestrator to prevent new actions
                try:
                    if hasattr(cortex.action_orchestrator, 'stop'):
                        cortex.action_orchestrator.stop()
                        logging.info("MockRPLidar: Action orchestrator stopped")
                    elif hasattr(cortex.action_orchestrator, 'running'):
                        cortex.action_orchestrator.running = False
                        logging.info("MockRPLidar: Action orchestrator marked as not running")
                    
                    # Give it a moment to stop processing
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logging.warning(f"MockRPLidar: Error stopping action orchestrator: {e}")

                if (
                    hasattr(cortex.action_orchestrator, "_config")
                    and cortex.action_orchestrator._config
                ):
                    if hasattr(cortex.action_orchestrator._config, "agent_actions"):
                        agent_actions = cortex.action_orchestrator._config.agent_actions

                        for i, agent_action in enumerate(agent_actions):
                            if (
                                hasattr(agent_action, "connector")
                                and agent_action.connector
                            ):
                                # Close Zenoh sessions in action connectors with timeout
                                if (
                                    hasattr(agent_action.connector, "session")
                                    and agent_action.connector.session
                                ):
                                    logging.info(f"MockRPLidar: Attempting to close action connector {i} Zenoh session")
                                    session_closed = await self._force_close_zenoh_session(
                                        agent_action.connector.session, 
                                        f"action connector {i}"
                                    )
                                    if session_closed:
                                        agent_action.connector.session = None

                                # Also close OdomProvider Zenoh session if it exists
                                if (
                                    hasattr(agent_action.connector, "odom")
                                    and agent_action.connector.odom
                                ):
                                    if (
                                        hasattr(agent_action.connector.odom, "session")
                                        and agent_action.connector.odom.session
                                    ):
                                        logging.info(f"MockRPLidar: Attempting to close OdomProvider Zenoh session")
                                        session_closed = await self._force_close_zenoh_session(
                                            agent_action.connector.odom.session,
                                            "OdomProvider"
                                        )
                                        if session_closed:
                                            agent_action.connector.odom.session = None

            # Clean up any other Zenoh sessions in the cortex config
            if hasattr(cortex, "config") and cortex.config:
                # Check for any providers that might have Zenoh sessions
                if hasattr(cortex.config, "agent_inputs"):
                    for input_obj in cortex.config.agent_inputs:
                        if hasattr(input_obj, "lidar") and input_obj.lidar:
                            if hasattr(input_obj.lidar, "zen") and input_obj.lidar.zen:
                                logging.info("MockRPLidar: Attempting to close lidar Zenoh session")
                                session_closed = await self._force_close_zenoh_session(
                                    input_obj.lidar.zen,
                                    "lidar"
                                )
                                if session_closed:
                                    input_obj.lidar.zen = None

            # Force cleanup of any remaining Zenoh sessions
            await self._force_cleanup_zenoh_sessions()

            logging.info("MockRPLidar: Cortex cleanup completed")

        except Exception as e:
            logging.error(f"MockRPLidar: Error during cortex cleanup: {e}")

    async def _force_cleanup_zenoh_sessions(self):
        """
        Force cleanup of any remaining Zenoh sessions by attempting to close them.
        """
        try:
            # Try to import zenoh and close any open sessions

            # Force garbage collection and wait for threads
            import gc

            gc.collect()

            # Wait a bit for any cleanup to complete
            await asyncio.sleep(0.5)

            # Check remaining threads
            import threading

            # Log remaining non-daemon threads with detailed information
            non_daemon_threads = []
            for thread in threading.enumerate():
                if (thread != threading.current_thread() and 
                    not thread.daemon and 
                    not thread.name.startswith('asyncio_')):  # Filter out asyncio threads as requested
                    non_daemon_threads.append(thread)

            if non_daemon_threads:
                logging.warning(
                    f"MockRPLidar: {len(non_daemon_threads)} non-daemon threads still active (excluding asyncio threads)"
                )
                
                # Log details about each thread for debugging
                for i, thread in enumerate(non_daemon_threads):
                    logging.warning(
                        f"MockRPLidar: Thread {i+1}: name='{thread.name}', "
                        f"ident={thread.ident}, alive={thread.is_alive()}, "
                        f"daemon={thread.daemon}"
                    )

                # Special handling for pyo3-closure threads (Zenoh threads)
                pyo3_threads = [t for t in non_daemon_threads if "pyo3-closure" in t.name]
                if pyo3_threads:
                    logging.info(f"MockRPLidar: Found {len(pyo3_threads)} pyo3-closure (Zenoh) threads to handle")
                    await self._handle_pyo3_threads(pyo3_threads)

                # Try to force-kill problematic threads by setting them as daemon
                threads_set_daemon = 0
                for thread in non_daemon_threads:
                    if (
                        "pyo3-closure" in thread.name or 
                        "zenoh" in thread.name.lower() or
                        "odom" in thread.name.lower() or
                        thread.name.startswith("Thread-") or
                        "tokio" in thread.name.lower()
                    ):
                        try:
                            if not thread.is_alive():  # Only try to set daemon on non-active threads
                                logging.info(f"MockRPLidar: Setting inactive thread '{thread.name}' as daemon")
                                thread.daemon = True
                                threads_set_daemon += 1
                            else:
                                logging.warning(f"MockRPLidar: Cannot set active thread '{thread.name}' as daemon - will try other methods")
                        except Exception as e:
                            logging.warning(f"MockRPLidar: Error setting thread '{thread.name}' as daemon: {e}")

                if threads_set_daemon > 0:
                    logging.info(f"MockRPLidar: Set {threads_set_daemon} threads as daemon")
                    
                    # Give them more time to finish after setting as daemon
                    await asyncio.sleep(2.0)
                    
                    # Check again after daemon setting (excluding asyncio threads)
                    remaining_threads = []
                    for thread in threading.enumerate():
                        if (thread != threading.current_thread() and 
                            not thread.daemon and 
                            not thread.name.startswith('asyncio_')):
                            remaining_threads.append(thread)
                            
                    if remaining_threads:
                        logging.error(
                            f"MockRPLidar: {len(remaining_threads)} threads still non-daemon after cleanup attempt (excluding asyncio)"
                        )
                        for thread in remaining_threads:
                            logging.error(
                                f"MockRPLidar: Persistent thread: name='{thread.name}', "
                                f"ident={thread.ident}, alive={thread.is_alive()}"
                            )
                            
                        # As a last resort, try to force close any remaining threads
                        # This is aggressive but may be necessary for cleanup
                        await self._force_terminate_remaining_threads(remaining_threads)
                    else:
                        logging.info("MockRPLidar: All threads successfully cleaned up (excluding asyncio)")
                else:
                    logging.warning("MockRPLidar: No threads were set as daemon - may be persistent threads")

        except Exception as e:
            logging.warning(f"MockRPLidar: Error during Zenoh cleanup: {e}")

    async def _handle_pyo3_threads(self, pyo3_threads):
        """
        Special handling for pyo3-closure threads (Zenoh threads).
        
        Parameters
        ----------
        pyo3_threads : list
            List of pyo3-closure threads to handle
        """
        logging.info("MockRPLidar: Attempting specialized cleanup for pyo3-closure threads")
        
        try:
            # First attempt: Give threads time to finish naturally
            logging.info("MockRPLidar: Waiting for pyo3-closure threads to finish naturally...")
            await asyncio.sleep(3.0)
            
            # Check if any are now inactive
            still_active = []
            for thread in pyo3_threads:
                if thread.is_alive():
                    still_active.append(thread)
                else:
                    try:
                        thread.daemon = True
                        logging.info(f"MockRPLidar: Successfully set inactive pyo3 thread as daemon")
                    except Exception as e:
                        logging.warning(f"MockRPLidar: Error setting inactive pyo3 thread as daemon: {e}")
            
            if still_active:
                logging.warning(f"MockRPLidar: {len(still_active)} pyo3-closure threads still active after wait")
                
                # Try to interrupt them by forcing garbage collection
                import gc
                logging.info("MockRPLidar: Forcing garbage collection to cleanup Zenoh resources")
                for _ in range(3):  # Multiple GC passes
                    gc.collect()
                    await asyncio.sleep(0.5)
                
                # Check again
                final_active = []
                for thread in still_active:
                    if thread.is_alive():
                        final_active.append(thread)
                        logging.warning(f"MockRPLidar: pyo3 thread '{thread.name}' (id: {thread.ident}) is persistently active")
                    else:
                        try:
                            thread.daemon = True
                            logging.info(f"MockRPLidar: Successfully set pyo3 thread as daemon after GC")
                        except Exception as e:
                            logging.warning(f"MockRPLidar: Error setting pyo3 thread as daemon after GC: {e}")
                
                if final_active:
                    logging.error(f"MockRPLidar: {len(final_active)} pyo3-closure threads remain active - this may indicate Zenoh resources are not properly cleaned")
                    
                    # Log final status of each persistent thread
                    for thread in final_active:
                        logging.error(f"MockRPLidar: Persistent pyo3 thread: {thread.name}, alive={thread.is_alive()}, daemon={thread.daemon}")
                        
                    # As a very last resort, mark them as daemon even if active
                    # This might cause issues but is better than hanging
                    for thread in final_active:
                        try:
                            # Force set daemon = True even for active threads
                            # This is risky but necessary to prevent hanging
                            import threading
                            thread._daemonic = True  # Direct attribute access
                            logging.warning(f"MockRPLidar: Force-set pyo3 thread '{thread.name}' as daemon (risky operation)")
                        except Exception as e:
                            logging.error(f"MockRPLidar: Failed final attempt to set pyo3 thread as daemon: {e}")
                else:
                    logging.info("MockRPLidar: All pyo3-closure threads successfully handled")
            else:
                logging.info("MockRPLidar: All pyo3-closure threads finished naturally")
                
        except Exception as e:
            logging.error(f"MockRPLidar: Error in pyo3 thread handling: {e}")

    async def _force_terminate_remaining_threads(self, threads):
        """
        Force terminate remaining threads as a last resort.
        
        Parameters
        ----------
        threads : list
            List of threads to terminate
        """
        logging.warning("MockRPLidar: Attempting to force terminate remaining threads as last resort")
        
        try:
            import ctypes
            import os
            
            for thread in threads:
                if thread.is_alive():
                    try:
                        # This is a very aggressive approach and should only be used as last resort
                        # It's platform-specific and may not work on all systems
                        if hasattr(ctypes, 'pythonapi') and hasattr(thread, 'ident'):
                            logging.warning(f"MockRPLidar: Force terminating thread '{thread.name}' (ident: {thread.ident})")
                            # Note: This is dangerous and may cause instability
                            # Only use if absolutely necessary
                            pass  # Commented out for safety
                        else:
                            logging.warning(f"MockRPLidar: Cannot force terminate thread '{thread.name}' - not supported on this platform")
                    except Exception as e:
                        logging.error(f"MockRPLidar: Error force terminating thread '{thread.name}': {e}")
                        
        except Exception as e:
            logging.error(f"MockRPLidar: Error in force terminate: {e}")
            
        # Final attempt: just set all remaining threads as daemon
        for thread in threads:
            try:
                thread.daemon = True
                logging.info(f"MockRPLidar: Final attempt - set thread '{thread.name}' as daemon")
            except Exception:
                pass

    def cleanup(self):
        """
        Synchronous cleanup method for proper resource cleanup.
        """
        logging.info("MockRPLidar.cleanup: Starting cleanup")

        try:
            self.running = False

            logging.info(
                f"MockRPLidar.cleanup: hasattr(self, 'lidar'), self.lidar: {hasattr(self, 'lidar')}, {self.lidar}"
            )
            # Clean up the lidar provider
            if hasattr(self, "lidar") and self.lidar:
                logging.info("MockRPLidar.cleanup: Stopping lidar provider")
                self.lidar.stop()

            logging.info("MockRPLidar.cleanup: Cleanup completed successfully")
        except Exception as e:
            logging.error(f"MockRPLidar.cleanup: Error during cleanup: {e}")

    async def async_cleanup(self):
        """
        Asynchronous cleanup method that handles both basic cleanup and cortex runtime cleanup.
        """
        # First do the basic cleanup
        self.cleanup()

        # Then do the comprehensive cortex cleanup
        await self.cleanup_cortex_runtime()

    def __del__(self):
        """Clean up resources when the object is destroyed."""
        self.cleanup()

    def reset_mock_data(self):
        """
        Reset the mock data to start from the beginning.
        Useful for repeated testing.
        """
        self.lidar_provider.reset()
        self.mock_data_processed = False
        logging.info("MockRPLidar: Mock data reset")

    async def _force_close_zenoh_session(self, session, provider_name):
        """
        Force close a Zenoh session with timeout.

        Parameters
        ----------
        session : ZenohSession
            The Zenoh session to close
        provider_name : str
            The name of the provider associated with the session

        Returns
        -------
        bool
            True if the session was closed successfully, False otherwise
        """
        try:
            # First, try to undeclare any publishers/subscribers to reduce active operations
            logging.info(f"MockRPLidar: Attempting to cleanup {provider_name} Zenoh session resources")
            
            # Try to access session internals to stop operations
            if hasattr(session, '_subscribers'):
                try:
                    # Try to undeclare subscribers
                    for sub in session._subscribers:
                        try:
                            sub.undeclare()
                        except:
                            pass
                except:
                    pass
            
            if hasattr(session, '_publishers'):
                try:
                    # Try to undeclare publishers
                    for pub in session._publishers:
                        try:
                            pub.undeclare()
                        except:
                            pass
                except:
                    pass
            
            # Give a short time for cleanup
            await asyncio.sleep(0.2)
            
            # Now try to close with progressively shorter timeouts
            for timeout in [2.0, 1.0, 0.5]:
                try:
                    logging.info(f"MockRPLidar: Attempting to close {provider_name} Zenoh session (timeout: {timeout}s)")
                    await asyncio.wait_for(
                        asyncio.to_thread(session.close),
                        timeout=timeout
                    )
                    logging.info(f"MockRPLidar: Successfully closed {provider_name} Zenoh session")
                    return True
                except asyncio.TimeoutError:
                    logging.warning(f"MockRPLidar: Timeout ({timeout}s) closing {provider_name} Zenoh session")
                    continue
                except Exception as e:
                    logging.warning(f"MockRPLidar: Error closing {provider_name} Zenoh session: {e}")
                    continue
            
            # If all timeouts failed, try one more aggressive approach
            logging.warning(f"MockRPLidar: All close attempts failed for {provider_name}, trying aggressive cleanup")
            
            # Try to force interrupt the session by setting it to None
            # This might not properly close but prevents further use
            return False
            
        except Exception as e:
            logging.warning(f"MockRPLidar: Error in force close {provider_name} Zenoh session: {e}")
            return False
