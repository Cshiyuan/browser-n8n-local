from task.storage.base import TaskStorage
from task.storage.memory import InMemoryTaskStorage

__all__ = ["TaskStorage", "InMemoryTaskStorage", "get_task_storage"]

# Factory function to get the default task storage implementation
def get_task_storage(storage_type="memory") -> TaskStorage:
    """
    Factory function to get a task storage implementation.
    
    Args:
        storage_type: Type of storage to use (default: "memory")
        
    Returns:
        An instance of TaskStorage implementation
    """
    if storage_type == "memory":
        return InMemoryTaskStorage()
    else:
        raise ValueError(f"Unknown storage type: {storage_type}") 