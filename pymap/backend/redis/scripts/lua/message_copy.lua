local uids_key = KEYS[1]
local dest_max_mod_key = KEYS[2]
local dest_uids_key = KEYS[3]
local dest_seq_key = KEYS[4]
local dest_mod_seq_key = KEYS[5]
local dest_recent_key = KEYS[6]
local dest_deleted_key = KEYS[7]
local dest_unseen_key = KEYS[8]
local flags_key = KEYS[9]
local immutable_key = KEYS[10]
local dest_flags_key = KEYS[11]
local dest_immutable_key = KEYS[12]
local content_data_key = KEYS[13]

local source_uid = ARGV[1]
local dest_uid = ARGV[2]
local msg_recent = tonumber(ARGV[3])

local uid_exists = redis.call('SISMEMBER', uids_key, source_uid)
if uid_exists == 0 then
    return redis.error_reply('message not found')
end

local msg_flags = redis.call('SMEMBERS', flags_key)
local msg_date = redis.call('HGET', immutable_key, 'time')
local msg_email_id = redis.call('HGET', immutable_key, 'emailid')
local msg_thread_id = redis.call('HGET', immutable_key, 'threadid')

local msg_deleted = false
local msg_unseen = true
for i, flag in ipairs(msg_flags) do
    if flag == '\\Deleted' then
        msg_deleted = true
    elseif flag == '\\Seen' then
        msg_unseen = false
    end
end

local dest_mod = redis.call('INCR', dest_max_mod_key)
redis.call('SADD', dest_uids_key, dest_uid)
redis.call('ZADD', dest_mod_seq_key, dest_mod, dest_uid)
redis.call('ZADD', dest_seq_key, dest_uid, dest_uid)

if msg_recent == 1 then
    redis.call('SADD', dest_recent_key, dest_uid)
end
if msg_deleted then
    redis.call('SADD', dest_deleted_key, dest_uid)
end
if msg_unseen then
    redis.call('ZADD', dest_unseen_key, dest_uid, dest_uid)
end
if #msg_flags > 0 then
    redis.call('SADD', dest_flags_key, unpack(msg_flags))
end

redis.call('HSET', dest_immutable_key, 'time', msg_date)
redis.call('HSET', dest_immutable_key, 'emailid', msg_email_id)
redis.call('HSET', dest_immutable_key, 'threadid', msg_thread_id)

redis.call('HINCRBY', content_data_key, 'refs', 1)

return redis.status_reply('OK')
