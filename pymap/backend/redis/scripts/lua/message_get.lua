local flags_key = KEYS[1]
local immutable_key = KEYS[2]

local uid = tonumber(ARGV[1])

local msg_flags = redis.call('SMEMBERS', flags_key)
local msg_time = redis.call('HGET', immutable_key, 'time')
local msg_email_id = redis.call('HGET', immutable_key, 'emailid')
local msg_thread_id = redis.call('HGET', immutable_key, 'threadid')

return {cjson.encode(msg_flags), msg_time, msg_email_id, msg_thread_id}
