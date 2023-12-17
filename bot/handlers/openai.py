import json

import requests

from bot.bot_settings import CHAT_GPT_API_KEY, CHAT_GPT_MODEL


def get_open_ai_answer(prompt:str):
	# делаем запрос на сервер с ключами
	response = requests.post(
		url='https://api.openai.com/v1/completions',
		headers={'Authorization': f'Bearer {CHAT_GPT_API_KEY}'},
		json={'model': CHAT_GPT_MODEL, 'prompt': prompt, 'temperature': 0.4, 'max_tokens': 300}
	)

	result = response.json()
	final_result = ''.join(choice['text'] for choice in result['choices'])
	return final_result


def get_open_ai_image(prompt:str):
	# запрос на  OpenAI API
	resp = requests.post(
		url='https://api.openai.com/v1/images/generations',
		headers={'Authorization': f'Bearer {CHAT_GPT_API_KEY}'},
		json={'prompt': prompt, 'n': 1, 'size': '1024x1024'}
	)
	response_text = json.loads(resp.text)

	return response_text['data'][0]['url']
