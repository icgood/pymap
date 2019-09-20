local mailboxes_key = KEYS[1]
local uid_validity_key = KEYS[2]

local name = ARGV[1]

local mbx_id = redis.call('HGET', mailboxes_key, name)

if not mbx_id then
    return redis.error_reply('mailbox not found')
end

local uid_validity = redis.call('HGET', uid_validity_key, name)

return {mbx_id, uid_validity}
