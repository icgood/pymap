local mailboxes_key = KEYS[1]
local order_key = KEYS[2]
local max_order_key = KEYS[3]
local uid_validity_key = KEYS[4]

local name = ARGV[1]
local mailbox_id = ARGV[2]

local exists = redis.call('HEXISTS', mailboxes_key, name)
if exists == 1 then
    return redis.error_reply('mailbox already exists')
end

local order = redis.call('INCR', max_order_key)
redis.call('HSET', mailboxes_key, name, mailbox_id)
redis.call('ZADD', order_key, order, mailbox_id)
redis.call('HINCRBY', uid_validity_key, name, 1)

return redis.status_reply('OK')
