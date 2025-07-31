Logging
=======

FlexEval uses Python’s :mod:`logging`.

If you're using logging but you don't want to see FlexEval's logs:

.. code-block:: python

    import logging
    # turn off all INFO and DEBUG log messages, but leave WARNING and ERROR messages
    logging.getLogger('flexeval').setLevel(logging.WARNING)
    # turn off all logging, including warnings and errors
    logging.getLogger('flexeval').setLevel(logging.CRITICAL + 1)

The :ref:`cli` has logging turned on by default.

If :mod:`flexeval.schema.config_schema.Config.logs_path` is set, logs will be written during eval execution.
