local i = nil
local i, uids_key = next(KEYS, i)
local i, seq_key = next(KEYS, i)
local i, content_key = next(KEYS, i)
local i, changes_key = next(KEYS, i)
local i, recent_key = next(KEYS, i)
local i, deleted_key = next(KEYS, i)
local i, unseen_key = next(KEYS, i)
local i, content_refs_key = next(KEYS, i)
local i, content_data_key = next(KEYS, i)

local uid = tonumber(ARGV[1])
local msg_recent = tonumber(ARGV[2])
local msg_flags_str = ARGV[3]
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

local msg_flags = cjson.decode(msg_flags_str)
local msg_deleted = false
local msg_seen = false
for i, flag in ipairs(msg_flags) do
    if flag == '\\Deleted' then
        msg_deleted = true
    elseif flag == '\\Seen' then
        msg_seen = true
    end
end

local message = cjson.encode({
    flags = msg_flags,
    date = msg_date,
    email_id = msg_email_id,
    thread_id = msg_thread_id,
})

redis.call('HSET', uids_key, uid, message)
redis.call('ZADD', seq_key, uid, uid)
redis.call('HSET', content_key, uid, msg_email_id)

redis.call('XADD', changes_key, 'MAXLEN', '~', 1000, '*',
    'uid', uid,
    'type', 'fetch',
    'message', message)

if msg_recent == 1 then
    redis.call('SADD', recent_key, uid)
end
if msg_deleted then
    redis.call('SADD', deleted_key, uid)
end
if not msg_seen then
    redis.call('ZADD', unseen_key, uid, uid)
end

redis.call('HINCRBY', content_refs_key, msg_email_id, 1)
redis.call('PERSIST', content_data_key)

return redis.status_reply('OK')
