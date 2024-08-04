import asyncio
import aiohttp
import json
import time
from urllib.parse import urlparse
from flask import Flask, request, render_template_string, jsonify, send_file

app = Flask(__name__)

async def fetch_data(session, url):
    try:
        async with session.get(url) as response:
            if response.status == 200:
                content_type = response.headers.get('Content-Type', '')
                if 'application/json' in content_type:
                    data = await response.json()
                else:
                    text_data = await response.text()
                    data = json.loads(text_data)

                extracted_data = []
                history = data.get('history', {})
                events = history.get('events', [])

                for event in events:
                    comment = event.get('comment', {})
                    created_at = comment.get('createdAt', None)
                    message = comment.get('message', None)
                    time_millis = event.get('timeMillis', None)

                    if created_at and message and time_millis is not None:
                        extracted_data.append({
                            'message': message,
                            'createdAt': created_at,
                            'timeMillis': time_millis
                        })
                return extracted_data
            else:
                print(f"Failed to fetch data: {response.status}")
                return []
    except Exception as e:
        print(f"Error occurred: {e}")
        return []

async def fetch_all_data(base_url, video_id, duration, interval=300):
    async with aiohttp.ClientSession() as session:
        tasks = []
        time_ranges = [(i, i + interval) for i in range(0, duration, interval)]

        for start_time, end_time in time_ranges:
            nonce = int(time.time() * 1000)
            url = f"{base_url}/userajax.php?c=history&m={video_id}&f={start_time}&t={end_time}&format=json&__n={nonce}&b=0&l=50"
            tasks.append(fetch_data(session, url))

        results = await asyncio.gather(*tasks)
        return [item for sublist in results for item in sublist]

@app.route('/fetch_comments', methods=['POST'])
def fetch_comments():
    url = request.form.get('url')
    if not url:
        return jsonify({'error': 'URL is required'}), 400

    parsed_url = urlparse(url)
    video_id = parsed_url.path.split('/')[-1]
    base_url = f"https://{parsed_url.netloc}"
    video_duration = 28800

    all_data = asyncio.run(fetch_all_data(base_url, video_id, video_duration))

    output_file = f"extracted_data_{video_id}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False)

    return render_template_string('''
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8">
        <title>Fetched Comments</title>
      </head>
      <body>
        <h1>Fetched Comments</h1>
        <pre>{{ data }}</pre>
        <form method="post" action="/save_comments">
            <input type="hidden" name="file_name" value="{{ file_name }}">
            <button type="submit">Save to File</button>
        </form>
      </body>
    </html>
    ''', data=json.dumps(all_data, indent=2, ensure_ascii=False), file_name=output_file)

@app.route('/save_comments', methods=['POST'])
def save_comments():
    file_name = request.form.get('file_name')
    return send_file(file_name, as_attachment=True)

@app.route('/')
def index():
    return '''
    <form method="post" action="/fetch_comments">
        <label for="url">TwitCasting URL:</label>
        <input type="text" id="url" name="url" required>
        <button type="submit">Fetch Comments</button>
    </form>
    '''

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
