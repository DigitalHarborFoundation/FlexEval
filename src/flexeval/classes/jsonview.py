import json
from collections import UserDict


class JsonViewDict(UserDict):
    """Dictionary that syncs changes back to the model field."""

    def __init__(
        self,
        model_instance,
        text_field_attr_name,
        json_dumps_fn=json.dumps,
        json_loads_fn=json.loads,
    ):
        self.model_instance = model_instance
        self.text_field_attr_name = text_field_attr_name
        self.json_dumps_fn = json_dumps_fn
        self.json_loads_fn = json_loads_fn

        text_value = getattr(model_instance, text_field_attr_name)
        initial_data = self.json_loads_fn(text_value)
        super().__init__(initial_data)

    def _sync_to_model(self):
        """Sync the current data back to the model field."""
        json_str = self.json_loads_fn(self.data)
        setattr(self.model_instance, self.text_field_attr_name, json_str)

    # Override mutating methods to trigger sync
    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self._sync_to_model()

    def __delitem__(self, key):
        super().__delitem__(key)
        self._sync_to_model()

    def clear(self):
        super().clear()
        self._sync_to_model()

    def pop(self, key, *args):
        result = super().pop(key, *args)
        self._sync_to_model()
        return result

    def popitem(self):
        result = super().popitem()
        self._sync_to_model()
        return result

    def setdefault(self, key, default=None):
        result = super().setdefault(key, default)
        self._sync_to_model()
        return result

    def update(self, *args, **kwargs):
        super().update(*args, **kwargs)
        self._sync_to_model()


class JsonView:
    """Descriptor that provides dict-like access to a JSON text field.

    Example:
    class SomeModel(pw.Model):
        some_field = pw.TextField(default="{}")
        some_field_dict = JsonView(text_field_attr_name="some_field")

    m = SomeModel()
    m.some_field_dict["chosen_mistake"] = "whatever"
    """

    def __init__(self, text_field_attr_name):
        self.text_field_attr_name = text_field_attr_name
        self.attr_name = None

    def __set_name__(self, owner, name):
        """Called when the descriptor is assigned to a class attribute."""
        self.attr_name = f"_{name}_dict"

    def __get__(self, instance, owner):
        if instance is None:
            return self

        # Check if we already have a cached JsonViewDict
        if not hasattr(instance, self.attr_name):
            if not hasattr(instance, self.text_field_attr_name):
                raise ValueError(
                    f"Failed to link this JsonView to field '{self.text_field_attr_name}' because it doesn't exist on this model instance."
                )
            # Cache a new JsonViewDict
            json_dict = JsonViewDict(instance, self.text_field_attr_name)
            setattr(instance, self.attr_name, json_dict)

        return getattr(instance, self.attr_name)

    def __set__(self, instance, value):
        """Allow setting the entire dict."""
        if isinstance(value, dict):
            json_dict = JsonViewDict(instance, self.text_field_attr_name)
            json_dict.update(value)
            setattr(instance, self.attr_name, json_dict)
        else:
            raise ValueError(
                f"This JsonView must be a dictionary to set linked field '{self.text_field_attr_name}' correctly."
            )
