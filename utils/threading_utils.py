import threading
from systemd import journal

def threading_function(function_name: callable, args=(), kwargs=None, name=None):
    if kwargs is None:
        kwargs = {}
    try:
        thread_name = name or f"Thread-{function_name.__name__}"
        t = threading.Thread(target=function_name, name=thread_name, args=args, kwargs=kwargs)
        t.daemon = True
        t.start()
        journal.send(f"Thread '{thread_name}' started successfully.")
        return t
    except Exception as e:
        journal.send(f"Error starting thread for '{function_name.__name__}': {e}")
        raise RuntimeError(f"Failed to start thread '{thread_name}'") from e
