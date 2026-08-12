import abc
import json
from typing import Any, Dict

DEFAULT_MODIFIED = "1970-01-01"


class BaseStorage(abc.ABC):
    @abc.abstractmethod
    def save_state(self, state: Dict[str, Any]) -> None:
        ...

    @abc.abstractmethod
    def retrieve_state(self) -> Dict[str, Any]:
        ...


class JsonFileStorage(BaseStorage):
    def __init__(self, file_path: str) -> None:
        self.file_path = file_path

    def save_state(self, state: Dict[str, Any]) -> None:
        with open(self.file_path, "w") as f:
            json.dump(state, f)

    def retrieve_state(self) -> Dict[str, Any]:
        try:
            with open(self.file_path, "r") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError):
            return {}


class State:
    def __init__(self, storage: BaseStorage) -> None:
        self.storage = storage
        self._state = self.storage.retrieve_state()

    def set_state(self, key: str, value: Any) -> None:
        self._state[key] = value
        self.storage.save_state(self._state)

    def get_state(self, key: str, default: Any = DEFAULT_MODIFIED) -> Any:
        return self._state.get(key, default)
