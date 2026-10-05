# Active production concurrency authority

The active rule is `HOST_SPECIFIC_QUALIFIED_CONCURRENCY`.

Historical W4/W6/W8 measurements and the former W8 recommendation remain
historical evidence. They are not a universal production worker-count
authority. A production request for `Workers=N` is permitted only when a
current host receipt binds the exact physical host, MATLAB/runtime identity,
protected authorities, qualified worker-local Simulink file-generation helper,
and successful 24-parent/96-run physical qualification to exactly `N` Process
workers. Capacity alone is never authority, and a receipt for one value of `N`
does not authorize another.

Production remains separately and explicitly armed per shard. A host receipt
does not itself start or generally authorize the campaign.
