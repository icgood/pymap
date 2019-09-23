local max_mod_key = KEYS[1]
local uids_key = KEYS[2]
local seq_key = KEYS[3]
local mod_seq_key = KEYS[4]
local recent_key = KEYS[5]
local deleted_key = KEYS[6]
local unseen_key = KEYS[7]
local expunged_key = KEYS[8]
local dest_max_mod_key = KEYS[9]
local dest_uids_key = KEYS[10]
local dest_seq_key = KEYS[11]
local dest_mod_seq_key = KEYS[12]
local dest_recent_key = KEYS[13]
local dest_deleted_key = KEYS[14]
local dest_unseen_key = KEYS[15]
local flags_key = KEYS[16]
local dates_key = KEYS[17]
local email_ids_key = KEYS[18]
local thread_ids_key = KEYS[19]
local dest_flags_key = KEYS[20]
local dest_dates_key = KEYS[19]
local dest_email_ids_key = KEYS[20]
local dest_thread_ids_key = KEYS[21]

local source_uid = ARGV[1]
local dest_uid = ARGV[2]
local msg_recent = tonumber(ARGV[3])

local uid_exists = redis.call('SISMEMBER', uids_key, source_uid)
if uid_exists == 0 then
    return redis.error_reply('message not found')
end

local mod = redis.call('INCR', max_mod_key)
redis.call('SREM', uids_key, source_uid)
redis.call('ZREM', mod_seq_key, source_uid)
redis.call('ZREM', seq_key, source_uid)
redis.call('SREM', recent_key, source_uid)
redis.call('SREM', deleted_key, source_uid)
redis.call('ZREM', unseen_key, source_uid)
redis.call('ZADD', expunged_key, mod, source_uid)

local msg_flags = redis.call('SMEMBERS', flags_key)
local msg_date = redis.call('HGET', dates_key, source_uid)
local msg_email_id = redis.call('HGET', email_ids_key, source_uid)
local msg_thread_id = redis.call('HGET', thread_ids_key, source_uid)

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
    redis.call('RENAME', flags_key, dest_flags_key)
end

redis.call('HSET', dest_dates_key, dest_uid, msg_date)
redis.call('HSET', dest_email_ids_key, dest_uid, msg_email_id)
redis.call('HSET', dest_thread_ids_key, dest_uid, msg_thread_id)

return redis.status_reply('OK')
