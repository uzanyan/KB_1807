
import requests
import csv
import matplotlib.pyplot as plt

def main(content, access_token):
    url = 'https://language.googleapis.com/v1/documents:analyzeSentiment?key={}'.format(access_token)
    header = {'Content-Type': 'application/json'}
    body = {
        "document": {
            "type": "PLAIN_TEXT",
            "language": "JA",
            "content": content
        },
        "encodingType": "UTF8"
    }
    response = requests.post(url, headers=header, json=body).json()
    print(content,response["documentSentiment"]["score"])
    return response["documentSentiment"]["score"]

if __name__ == '__main__':
    with open('LINEDATA.csv', 'r',encoding="utf-8_sig") as f:
        reader = csv.DictReader(f)
        score_list = []
        time_list = []
        for row in reader:
            #text_list.append(row["text (S)"])
            score = main(row["text (S)"], "AIzaSyAoygcEiRIojkk1N43gAk8aBnembCxvBHw")
            score_list.append(score)
            time_list.append(row["date (S)"])
        print(score_list)
        plt.plot(time_list,score_list)
        plt.xlabel("time")
        plt.ylabel("score")
        plt.title("negapogi")
        plt.show()
