local max_uid_key = KEYS[1]
local email_ids_key = KEYS[2]
local thread_ids_key = KEYS[3]

local new_email_id = ARGV[1]
local new_thread_id = ARGV[2]
local content_hash = ARGV[3]
local thread_keys = cjson.decode(ARGV[4])

local new_uid = redis.call('INCR', max_uid_key)

redis.call('HSETNX', email_ids_key, content_hash, new_email_id)
local email_id = redis.call('HGET', email_ids_key, content_hash)
local new_content = (email_id == new_email_id) or 0

local thread_id = new_thread_id
for i, thread_key in ipairs(thread_keys) do
    local thread_key_id = redis.call('HGET', thread_ids_key, thread_key)
    if thread_key_id then
        thread_id = thread_key_id
        break
    end
end
for i, thread_key in ipairs(thread_keys) do
    redis.call('HSET', thread_ids_key, thread_key, thread_id)
end

return {new_uid, email_id, thread_id, new_content}
