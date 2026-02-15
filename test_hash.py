from werkzeug.security import check_password_hash

hash_value = "PASTE_THE_HASH_FROM_MYSQL_HERE"

print(check_password_hash(hash_value, "1234"))
