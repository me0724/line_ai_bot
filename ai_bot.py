import os
import sys

from flask import Flask, request, abort

from linebot.v3 import WebhookHandler

from linebot.v3.webhooks import MessageEvent, TextMessageContent, UserSource
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, TextMessage, ReplyMessageRequest
from linebot.v3.exceptions import InvalidSignatureError

from openai import AzureOpenAI

# get LINE credentials from environment variables
channel_access_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
channel_secret = os.environ["LINE_CHANNEL_SECRET"]

if channel_access_token is None or channel_secret is None:
    print("Specify LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET as environment variable.")
    sys.exit(1)

# get Azure OpenAI credentials from environment variables
azure_openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
azure_openai_api_key = os.getenv("AZURE_OPENAI_API_KEY")
azure_openai_api_version = os.getenv("AZURE_OPENAI_API_VERSION")
azure_openai_model = os.getenv("AZURE_OPENAI_MODEL")

if azure_openai_endpoint is None or azure_openai_api_key is None or azure_openai_api_version is None:
    raise Exception(
        "Please set the environment variables AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, and AZURE_OPENAI_API_VERSION."
    )


handler = WebhookHandler(channel_secret)
configuration = Configuration(access_token=channel_access_token)

app = Flask(__name__)
ai = AzureOpenAI(
    azure_endpoint=azure_openai_endpoint, api_key=azure_openai_api_key, api_version=azure_openai_api_version
)

# UNISON SQUARE GARDENに関する質問と回答データ
UNISON_FAQ = {
    "メンバー": "メンバーは斎藤宏介さん（ボーカル・ギター）、田淵智也さん（ベース）、鈴木貴雄さん（ドラム）やで！",
    "代表曲": "代表曲は『シュガーソングとビターステップ』や『オリオンをなぞる』やで！",
    "デビュー": "UNISON SQUARE GARDENは2004年に結成され、2008年に「センチメンタルピリオド」でメジャーデビューしたんや。",
    "最新アルバム": "最新アルバムは『SUB MACHINE, BEST MACHINE』やで！結成20周年を記念してリリースされたやつで、昔の曲たちも再録されてる素晴らしいアルバムなんや！ぜひ聴いてみてな🎵",
    "ライブ": "公式サイトやSNSで最新のライブ情報をチェックしてな！公式サイトはこちら：https://unison-s-g.com/",
}

chat_history = []


# LINEボットからのリクエストを受け取るエンドポイント
@app.route("/callback", methods=["POST"])
def callback():
    # get X-Line-Signature header value
    signature = request.headers["X-Line-Signature"]

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError as e:
        abort(400, e)

    return "OK"






# 　AIへのメッセージを初期化する関数
def init_chat_history():
    chat_history.clear()
    system_role = {
        "role": "system",
        "content":(
            "UNISON SQUARE GARDENについて何でも聞いてな！\n"
            "例えばこんな質問ができるで:\n"
            "- メンバーは誰？\n"
            "- 代表曲を教えて！\n"
            "- デビューしたのはいつ？\n"
            "- 最新アルバムは？\n"
            "- ライブ情報を教えて！\n"
        ),
    }
    chat_history.append(system_role)

def get_unison_info(question):
    print(f"ユーザーの質問: {question}")  # デバッグ用ログ
    question = question.lower()  # 小文字化して比較
    for key in UNISON_FAQ:
        if key.lower() in question:  # 部分一致の確認
            print(f"一致したキー: {key}")  # デバッグ用ログ
            return UNISON_FAQ[key]
    return "UNISON SQUARE GARDENについての質問がよくわからへんかったわ…別の質問をしてみてな！🎵"




def get_ai_response(from_user, text):
    user_msg = {"role": "user", "content": text}
    chat_history.append(user_msg)
    parameters = {"model": azure_openai_model, "max_tokens": 100, "temperature": 0.5, "frequency_penalty": 0, "presence_penalty": 0}
    ai_response = ai.chat.completions.create(messages=chat_history, **parameters)
    res_text = ai_response.choices[0].message.content
    ai_msg = {"role": "assistant", "content": res_text}
    chat_history.append(ai_msg)
    return res_text

def generate_response(from_user, text):
    if text in ["リセット", "初期化", "クリア", "reset", "clear"]:
        init_chat_history()
        return [TextMessage(text="チャットをリセットしました。")]
    elif "UNISON" in text or "ユニゾン" in text:
        info = get_unison_info(text)
        return [TextMessage(text=info)]
    else:
        return [TextMessage(text=get_ai_response(from_user, text))]

@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    text = event.message.text
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        res = []
        if isinstance(event.source, UserSource):
            profile = line_bot_api.get_profile(event.source.user_id)
            res = generate_response(profile.display_name, text)
        else:
            res = [TextMessage(text="ユーザー情報を取得できませんでした。"), TextMessage(text=f"メッセージ：{text}")]
        line_bot_api.reply_message_with_http_info(ReplyMessageRequest(reply_token=event.reply_token, messages=res))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)


