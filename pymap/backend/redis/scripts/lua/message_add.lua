local max_mod_key = KEYS[1]
local uids_key = KEYS[2]
local mod_seq_key = KEYS[3]
local seq_key = KEYS[4]
local recent_key = KEYS[5]
local deleted_key = KEYS[6]
local unseen_key = KEYS[7]
local flags_key = KEYS[8]
local immutable_key = KEYS[9]
local content_data_key = KEYS[10]

local uid = tonumber(ARGV[1])
local msg_recent = tonumber(ARGV[2])
local msg_flags = cjson.decode(ARGV[3])
local msg_date = ARGV[4]
local msg_email_id = ARGV[5]
local msg_thread_id = ARGV[6]

if #ARGV > 6 then
    local message = ARGV[7]
    local message_json = ARGV[8]
    local header = ARGV[9]
    local header_json = ARGV[10]
    redis.call('HSET', content_data_key, 'full', message)
    redis.call('HSET', content_data_key, 'full-json', message_json)
    redis.call('HSET', content_data_key, 'header', header)
    redis.call('HSET', content_data_key, 'header-json', header_json)
end

local msg_deleted = false
local msg_unseen = true
for i, flag in ipairs(msg_flags) do
    if flag == '\\Deleted' then
        msg_deleted = true
    elseif flag == '\\Seen' then
        msg_unseen = false
    end
end

local mod_seq = redis.call('INCR', max_mod_key)
redis.call('SADD', uids_key, uid)
redis.call('ZADD', mod_seq_key, mod_seq, uid)
redis.call('ZADD', seq_key, uid, uid)

if msg_recent == 1 then
    redis.call('SADD', recent_key, uid)
end
if msg_deleted then
    redis.call('SADD', deleted_key, uid)
end
if msg_unseen then
    redis.call('ZADD', unseen_key, uid, uid)
end
if #msg_flags > 0 then
    redis.call('SADD', flags_key, unpack(msg_flags))
end

redis.call('HSET', immutable_key, 'time', msg_date)
redis.call('HSET', immutable_key, 'emailid', msg_email_id)
redis.call('HSET', immutable_key, 'threadid', msg_thread_id)

redis.call('HINCRBY', content_data_key, 'refs', 1)
redis.call('PERSIST', content_data_key)

return redis.status_reply('OK')
