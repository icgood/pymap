local flags_key = KEYS[1]
local immutable_key = KEYS[2]
local uids_key = KEYS[3]
local deleted_key = KEYS[4]
local unseen_key = KEYS[5]

local uid = tonumber(ARGV[1])
local mode = ARGV[2]
local flag_set = cjson.decode(ARGV[3])

local uid_exists = redis.call('SISMEMBER', uids_key, uid)

if uid_exists == 1 then
    local has_deleted = false
    local has_seen = false
    for i, flag in ipairs(flag_set) do
        if flag == '\\Deleted' then
            has_deleted = true
        elseif flag == '\\Seen' then
            has_seen = true
        end
    end

    if mode == 'ADD' and #flag_set > 0 then
        redis.call('SADD', flags_key, unpack(flag_set))

        if has_deleted then
            redis.call('SADD', deleted_key, uid)
        end
        if has_seen then
            redis.call('ZREM', unseen_key, uid)
        end
    elseif mode == 'DELETE' and #flag_set > 0 then
        redis.call('SREM', flags_key, unpack(flag_set))

        if has_deleted then
            redis.call('SREM', deleted_key, uid)
        end
        if has_seen then
            redis.call('ZADD', unseen_key, uid, uid)
        end
    elseif mode == 'REPLACE' then
        redis.call('DEL', flags_key)
        if #flag_set > 0 then
            redis.call('SADD', flags_key, unpack(flag_set))
        end

        if has_deleted then
            redis.call('SADD', deleted_key, uid)
        else
            redis.call('SREM', deleted_key, uid)
        end
        if has_seen then
            redis.call('ZREM', unseen_key, uid)
        else
            redis.call('ZADD', unseen_key, uid, uid)
        end
    end
end

local msg_flags = redis.call('SMEMBERS', flags_key)
local msg_time = redis.call('HGET', immutable_key, 'time')
local msg_email_id = redis.call('HGET', immutable_key, 'emailid')
local msg_thread_id = redis.call('HGET', immutable_key, 'threadid')

return {cjson.encode(msg_flags), msg_time, msg_email_id, msg_thread_id}
