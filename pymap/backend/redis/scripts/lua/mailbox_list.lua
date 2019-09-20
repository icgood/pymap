local mailboxes_key = KEYS[1]
local order_key = KEYS[2]

local mailboxes = redis.call('HGETALL', mailboxes_key)
local order = redis.call('ZRANGE', order_key, 0, -1)

return {mailboxes, order}
