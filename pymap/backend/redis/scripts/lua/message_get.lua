local flags_key = KEYS[1]
local dates_key = KEYS[2]
local email_ids_key = KEYS[3]
local thread_ids_key = KEYS[4]
local uids_key = KEYS[5]

local uid = tonumber(ARGV[1])

local uid_exists = redis.call('SISMEMBER', uids_key, uid)
if uid_exists == 0 then
    return redis.error_reply('message not found')
end

local msg_flags = redis.call('SMEMBERS', flags_key)
local msg_time = redis.call('HGET', dates_key, uid)
local msg_email_id = redis.call('HGET', email_ids_key, uid)
local msg_thread_id = redis.call('HGET', thread_ids_key, uid)

return {cjson.encode(msg_flags), msg_time, msg_email_id, msg_thread_id}
