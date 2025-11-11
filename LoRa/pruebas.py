RELAY_BIT = 1            # Relay flag
TYPE_MSG = 1             # Message type
print(bin(RELAY_BIT << 7 | (TYPE_MSG & 0x7F))),                # Message type
command = '{"T":1,"L":1,"R":1}\n'
data = command.encode('utf-8')
print(' '.join(f'{b:08b}' for b in data))
print(len(data))