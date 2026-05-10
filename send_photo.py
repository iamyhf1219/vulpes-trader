import json
import urllib.request
import os

# Read bot token from config
with open(os.path.expanduser(r'~/.openclaw/openclaw.json'), 'r') as f:
    config = json.load(f)

token = config['channels']['telegram']['botToken']
chat_id = '6220243218'

# Send photo using multipart/form-data
boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
photo_path = os.path.expanduser(r'~/.openclaw/workspace/bilibili_home_thumb.jpg')

with open(photo_path, 'rb') as f:
    photo_data = f.read()

body = []
body.append(f'--{boundary}'.encode())
body.append('Content-Disposition: form-data; name="chat_id"'.encode())
body.append(b'')
body.append(chat_id.encode())
body.append(f'--{boundary}'.encode())
body.append(f'Content-Disposition: form-data; name="photo"; filename="bilibili.jpg"'.encode())
body.append('Content-Type: image/jpeg'.encode())
body.append(b'')
body.append(photo_data)
body.append(f'--{boundary}--'.encode())
body.append(b'')

data = b'\r\n'.join(body)

url = f'https://api.telegram.org/bot{token}/sendPhoto'
req = urllib.request.Request(url, data=data)
req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
req.add_header('Content-Length', str(len(data)))

try:
    resp = urllib.request.urlopen(req)
    result = json.loads(resp.read())
    if result.get('ok'):
        print('图片发送成功!')
    else:
        print(f'发送失败: {result}')
except urllib.error.HTTPError as e:
    print(f'HTTP Error: {e.code} - {e.read().decode()}')
except Exception as e:
    print(f'Error: {e}')
