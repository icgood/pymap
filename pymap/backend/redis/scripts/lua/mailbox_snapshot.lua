local max_uid_key = KEYS[1]
local uids_key = KEYS[2]
local seq_key = KEYS[3]
local recent_key = KEYS[4]
local unseen_key = KEYS[5]

local next_uid = (redis.call('GET', max_uid_key) or 0) + 1
local num_exists = redis.call('SCARD', uids_key)
local num_recent = redis.call('SCARD', recent_key)
local num_unseen = redis.call('ZCARD', unseen_key)

local first_unseen
if num_unseen > 0 then
    local first_unseen_uids = redis.call('ZRANGE', unseen_key, 0, 0)
    first_unseen = redis.call('ZRANK', seq_key, first_unseen_uids[1])
else
    first_unseen = ''
end

return {next_uid, num_exists, num_recent, num_unseen, first_unseen}
