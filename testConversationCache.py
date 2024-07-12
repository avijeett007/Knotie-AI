from ConversationCache import CacheManager

conversation_cache = CacheManager()

if conversation_cache.get("Test") is None:
    conversation_cache.put("Test", "Yes is test")
if conversation_cache.get("Testing") is None:
    conversation_cache.put("Testing", "Is that testing?")
if conversation_cache.get("Testing of telecom") is None:
    conversation_cache.put("Testing of telecom", "Is that testing?")


print(conversation_cache.search("Test"))
print(conversation_cache.search("Testing"))
print(conversation_cache.search("Testing of telecom"))
print(conversation_cache.search("Testing telecom"))
print(conversation_cache.search("Testing an telecom"))
print(conversation_cache.search("Testing the telecom"))
print(conversation_cache.search("Test the telecom"))
print(conversation_cache.search("about telecom"))
