from fastai.text import *
import re
class Analyse:
    def __init__(self, folder_path, model_file):
        # specify path
        path = Path(folder_path)
        # load in csv
        df = pd.read_csv(path/'Tweets.csv')
        #print(df.head())

        # split df into training and validation
        train_df, valid_df = df.loc[:12000,:], df.loc[12000:,:]

        # create databunches
        data_lm = TextLMDataBunch.from_df(path, train_df, valid_df, text_cols=10, bs=32)
        data_clas = TextClasDataBunch.from_df(path, train_df, valid_df, text_cols=10, label_cols=1, bs=32)

        data_lm.show_batch()

        data_clas.show_batch()

        learn = language_model_learner(data_lm, AWD_LSTM, drop_mult=0.3)
        learn.load('fit_head')
        TEXT = "Cameroon is a beautiful "
        N_WORDS = 40
        N_SENTENCES = 2
        print("\n".join(learn.predict(TEXT, N_WORDS, temperature=0.75) for _ in range(N_SENTENCES)))

        # save encoder
        learn.save_encoder('twitter-sentiment-enc')

        # create model and load in encoder
        self.learn = text_classifier_learner(data_clas, AWD_LSTM, drop_mult=0.3)
        self.learn.load_encoder('twitter-sentiment-enc')
        self.learn.load(model_file)
    
    def predict_sentiment(self, dataset):
        analysed_data = dataset
        result = []
        sentiments = []
        for i, status in enumerate(analysed_data):
            analysed_data[i].sentiment = self.learn.predict(dataset[i].text)
            conf = re.findall(r'\d+\.\d+e?-?\d+',str(analysed_data[i].sentiment[2]))
            conf1 = {'id':analysed_data[i].id, 'lang':analysed_data[i].lang, 'created_at': dataset[i].created_at,'retweet_count':analysed_data[i].retweet_count, 'favorite_count':analysed_data[i].favorite_count, 'text': analysed_data[i].text, 'username': analysed_data[i].user.name, 'category': str(analysed_data[i].sentiment[0]),  'neg':float(conf[0]), 'neu':float(conf[1]), 'pos':float(conf[2])}
            #conf1 = {'id':analysed_data[i].id, 'lang':analysed_data[i].lang, 'created_at': dataset[i].created_at,'retweet_count':analysed_data[i].retweet_count, 'favorite_count':analysed_data[i].favorite_count, 'text': analysed_data[i].text, 'user': analysed_data[i].user, 'category': analysed_data[i].sentiment[0], 'neg':float(conf[0]), 'neu':float(conf[1]), 'pos':float(conf[2])}
            sentiments.append(conf1)
            #result.append({'id':analysed_data[i].id, 'lang':analysed_data[i].lang, 'retweet_count':analysed_data[i].retweet_count, 'favorite_count':analysed_data[i].favorite_count, 'text': analysed_data[i].text, 'user': analysed_data[i].user, 'created_at': analysed_data[i].created_at, 'category': analysed_data[i].sentiment[0], 'confidence': conf1})
            print(str(analysed_data[i].sentiment[0]))
            #analysed_data[i].sentiment[2] = re.findall(r'\d+\.\d+e?-?\d+',str(analysed_data[i].sentiment[2]))
        return sentiments