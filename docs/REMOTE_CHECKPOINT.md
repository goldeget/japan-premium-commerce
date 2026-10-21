# Remote checkpoint verification

This small checkpoint is the first remote-write test required by the KURANEA
development directive. It intentionally contains no application code.

After pushing this commit to `work`, verify recovery by cloning `work` into a
fresh temporary checkout, confirming this file is present, and comparing that
checkout's `HEAD` with the remote branch SHA.
