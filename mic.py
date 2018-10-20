
import pyaudio, time, audioop, math, sys, argparse, matplotlib,requests,json,pprint
from gcloud.credentials import get_credentials
from google.cloud.speech.v1beta1 import cloud_speech_pb2
from google.rpc import code_pb2
from grpc.beta import implementations

class stdout:
	BOLD = "\033[1m"
	END = "\033[0m"
	CLEAR = "\033[2K"

def bold(string):
	return string#stdout.BOLD + string + stdout.END

def printr(string):
	sys.stdout.write("\r")
	#sys.stdout.write("\r" + stdout.CLEAR)
	sys.stdout.write(string)
	sys.stdout.flush()

frames = []
silent_frames = []
is_recording = False
should_finish_stream = False

class Result:
	def __init__(self):
		self.transcription = ""
		self.confidence = ""
		self.is_final = False

recognition_result = Result()

def make_channel(host, port):
	ssl_channel = implementations.ssl_channel_credentials(None, None, None)
	creds = get_credentials().create_scoped(args.speech_scope)
	auth_header = ("authorization", "Bearer " + creds.get_access_token().access_token)
	auth_plugin = implementations.metadata_call_credentials(lambda _, func: func([auth_header], None), name="google_creds")
	composite_channel = implementations.composite_channel_credentials(ssl_channel, auth_plugin)
	return implementations.secure_channel(host, port, composite_channel)

def listen_loop(recognize_stream):
	global should_finish_stream
	global recognition_result

	for resp in recognize_stream:
		if resp.error.code != code_pb2.OK:
			raise RuntimeError(resp.error.message)#raise?

		for result in resp.results:
			for alt in result.alternatives:
				recognition_result.transcription = alt.transcript
				recognition_result.confidence = alt.confidence
				recognition_result.stability = result.stability
				#リアルタイムで表示する

				printr(" ".join((alt.transcript))) #"	",
				#"stability: ", str(int(result.stability * 100)), "%",
				#"time: ",time.strftime("%H:%M:%S"))))

			#ここで一言を言い終える
			if result.is_final:
				recognition_result.is_final = True
				should_finish_stream = True
				return

def request_stream():
	recognition_config = cloud_speech_pb2.RecognitionConfig(
		encoding=args.audio_encoding,
		sample_rate=args.sampling_rate,
		language_code=args.lang_code,
		max_alternatives=1,
	)
	streaming_config = cloud_speech_pb2.StreamingRecognitionConfig(
		config=recognition_config,
		interim_results=True,
		single_utterance=True
	)

	yield cloud_speech_pb2.StreamingRecognizeRequest(streaming_config=streaming_config)

	while True:
		time.sleep(args.frame_seconds / 4)

		if should_finish_stream:
			return

		if len(frames) > 0:
			yield cloud_speech_pb2.StreamingRecognizeRequest(audio_content=frames.pop(0))

def pyaudio_callback(in_data, frame_count, time_info, status):
	# in_data = b"".join(in_data)
	assert isinstance(in_data, bytes)
	frames.append(in_data)
	return (None, pyaudio.paContinue)

def run_recognition_loop():
	global frames
	global silent_frames
	global is_recording
	global should_finish_stream

	if len(silent_frames) > 4:
		silent_frames = silent_frames[-4:]
		#print ("silent_frames:",silent_frames)

	while not is_recording:
		#print("---sleep---")
		time.sleep(args.frame_seconds // 4)#処理を一時停止する
		#print("----on-----")
		#なんのif文かわからん
		if len(frames) > 4:
			for frame_index in range(4):
				data = frames[frame_index]
				rms = audioop.rms(data, 2)
				decibel = 20 * math.log10(rms) if rms > 0 else 0
				if decibel < args.silent_decibel:
					silent_frames += frames[0:frame_index+1]
					del frames[0:frame_index + 1] #リストの部分を削除
					return

			is_recording = True
			frames = silent_frames + frames
			silent_frames = []

	#音声をテキストにする
	with cloud_speech_pb2.beta_create_Speech_stub(make_channel(args.host,args.ssl_port)) as service: #このフォルダをservice関数に入れる
		try:
			#ここで録音して変換している
			print("処理中")
			listen_loop(service.StreamingRecognize(request_stream(), args.deadline_seconds))

			#最終的な結果はここ
			printr(" ".join((bold(recognition_result.transcription))))#"	",
			#"confidence: ", str(int(recognition_result.confidence * 100)), "%",
			#"time: ",time.strftime("%H:%M:%S"))))
			list = {"ID":ID,
			"trans": recognition_result.transcription,
			"confidence": recognition_result.confidence * 100,
			"time": time.strftime("%H:%M:%S")}
			json_data = json.dumps(list)
			response = requests.post(
		        'https://2dhdoj4j8c.execute-api.ap-northeast-1.amazonaws.com:443/dev/datadump',
		        json_data)
			#pprint.pprint(response.json())
			print()
		except Exception as e:
			print(str(e))

def main():
	global is_recording
	global should_finish_stream
	global ID
	#音の定義，
	pa = pyaudio.PyAudio()
	#デバイスの定義
	devices = []
	for device_index in range(pa.get_device_count()):
		metadata = pa.get_device_info_by_index(device_index)
		print(device_index, metadata["name"])

	stream = pa.open(format=pa.get_format_from_width(2),
					channels=1,
					rate=args.sampling_rate,
					input_device_index=args.device_index,
					input=True,
					output=False,
					frames_per_buffer=int(args.sampling_rate * args.frame_seconds),
					stream_callback=pyaudio_callback)

	stream.start_stream()

	#-------------録音開始--------------
	ID = input("IDを入力してください>>>")
	RECORD_SECONDS = input("録音する長さを押してください>>>")
	#時間の計測
	t1 = time.time()
	while True:
		is_recording = False
		should_finish_stream = False
		t2 = time.time()
		elapsed_time = t2-t1 #経過時間
		if float(elapsed_time) > float(RECORD_SECONDS):
			#print("経過時間:",elapsed_time)
			break
		run_recognition_loop()
	print("録音終了")
	stream.stop_stream()
	stream.close()

	#-------------録音停止--------------
	pa.terminate()

if __name__ == "__main__":
	parser = argparse.ArgumentParser() #コマンドライン上で引数を受け取る
	parser.add_argument("--sampling-rate", "-rate", type=int, default=16000)
	parser.add_argument("--device-index", "-device", type=int, default=1)#デバイス　０パソコン　１マイク
	parser.add_argument("--lang-code", "-lang", type=str, default="ja-JP") #日本語
	parser.add_argument("--audio-encoding", "-encode", type=str, default="LINEAR16")
	parser.add_argument("--frame-seconds", "-fsec", type=float, default=0.1, help="1フレームあたりの時間（秒）. デフォルトは100ミリ秒")
	parser.add_argument("--deadline-seconds", "-dsec", type=int, default=60*3+5) #ここが1言の終了条件
	parser.add_argument("--silent-decibel", "-decibel", type=int, default=10)
	parser.add_argument("--speech-scope", "-scope", type=str, default="https://www.googleapis.com/auth/cloud-platform")
	parser.add_argument("--ssl-port", "-port", type=int, default=443)
	parser.add_argument("--host", "-host", type=str, default="speech.googleapis.com")
	args = parser.parse_args()#引数を解析する
	main()
