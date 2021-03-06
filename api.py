import flask
import sqlite3
from flask import Flask, jsonify, request, render_template
from flask_sqlalchemy import SQLAlchemy
import datetime 
import os
import joblib
import pandas as pd
import numpy as np 

app = Flask(__name__)

print("Database URL: ", os.environ.get('DATABASE_URL', 'postgresql://hunterowens:@localhost/hunterowens'))

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'postgresql://hunterowens:@localhost/hunterowens')
db = SQLAlchemy(app)

class State(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_date = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    sentiment = db.Column(db.Float)
    focus = db.Column(db.Float)
    energy = db.Column(db.Float)
    text = db.Column(db.String(5000))

class FormData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_date = db.Column(db.DateTime, default=datetime.datetime.now())
    data = db.Column(db.JSON)

class Sentence(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_date = db.Column(db.DateTime, default=datetime.datetime.now())
    text = db.Column(db.String(5000))
    cat = db.Column(db.String(50))

class Sentence_Shelly(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_date = db.Column(db.DateTime, default=datetime.datetime.now())
    text = db.Column(db.String(5000))
    cat = db.Column(db.String(50))

@app.route('/')
def test():
    """
    fake home                 
    """
    return "Test works"

@app.route("/reset")
def reset():
    """
    Resets the state and API to null
    """
    s = State(sentiment=0, focus=0, energy=0, text="reset_triggered")
    db.session.add(s)
    db.session.commit()
    return "Reset the state to 0"

@app.route("/interact", methods=['GET','POST'])
def interact():
    """
    Interact with the API. 

    When post, either submits Surface Data (as JSON) or text content from Audience. 
    Post then updates state db. 

    Get requests returns AI state, possible text and next question all as JSON
    """
    if request.method == 'POST':
        data = request.get_json(force=True)
        senti_model = joblib.load(open('./saved/m_senti.p', 'rb'))
        focus_model = joblib.load(open('./saved/m_focus.p','rb'))
        energy_model = joblib.load(open('./saved/m_energy.p','rb'))
        string = data['string']
        # print(data)
        # print(string)
        def get_pred(model, string):
            return model.predict([string])[0]
        s = State(sentiment=get_pred(senti_model, string),
                  focus = get_pred(focus_model, string),
                  energy = get_pred(energy_model, string),
                  text = string)
        db.session.add(s)
        db.session.commit()
        # print('saved ', s)
        return "saved interact"
    elif request.method == 'GET':
        ## Get most recent state info
        s = State.query.order_by(State.created_date.desc()).first()
        data={}
        data['sentiment'] = s.sentiment
        data['focus'] = s.focus
        data['energy'] = s.energy
        # parse the text into a catagory
        text = s.text
        le = joblib.load(open('./saved/classes.p','rb'))
        cat_model = joblib.load(open('./saved/cat_model.p','rb'))
        probs = pd.concat([pd.Series(le), pd.Series(cat_model.predict_proba([text])[0])], axis=1)
        list_probs = list(probs.sort_values(by=[1], ascending=False)[0][:3]) 
        cat = list_probs[0]
        data['state'] = list_probs[0]
        data['state2'] = list_probs[1]
        data['state3'] = list_probs[2]
        data['text'] = text
        # start making new text and questions
        #if os.path.exists('./saved/faken-markov/' + cat + '.p'):
        #    f_mark = joblib.load(open('./saved/faken-markov/' + cat + '.p', 'rb'))
        #    data['sentence'] = f_mark.make_sentence()
        #else:
        #    f_mark = joblib.load(open('./saved/faken-markov/connected.p', 'rb'))
        #    data['sentence'] = f_mark.make_sentence()

        # quetion time

        if os.path.exists('./saved/faken-questions/' + cat + '.p'):
            f_mark = joblib.load(open('./saved/faken-questions/' + cat + '.p', 'rb'))
            data['questions'] = {i: f_mark.make_sentence() for i in range(4)}
        else:
            f_mark = joblib.load(open('./saved/faken-questions/guarded.p', 'rb'))
            data['questions'] = {i: f_mark.make_sentence() for i in range(4)}
        
        return jsonify(data)

@app.route("/interact-surface", methods=['POST'])
def interact_surface():
    data = request.get_json(force=True)
    s = State(sentiment=data['sentiment'],
              focus = data['focus'],
              energy = data['energy'],
              text = "surface text")
    db.session.add(s)
    db.session.commit()
    return "surface data saved"

@app.route("/talk", methods=["GET"])
def talk():
    s = State.query.order_by(State.created_date.desc()).first()
    data={}
    data['sentiment'] = s.sentiment
    data['focus'] = s.focus
    data['energy'] = s.energy
    # parse the text into a catagory
    text = s.text
    le = joblib.load(open('./saved/classes.p','rb'))
    cat_model = joblib.load(open('./saved/cat_model.p','rb'))
    probs = pd.concat([pd.Series(le), pd.Series(cat_model.predict_proba([text])[0])], axis=1)
    list_probs = list(probs.sort_values(by=[1], ascending=False)[0][:3]) 
    cat = list_probs[0]
    data['state'] = list_probs[0]
    data['state2'] = list_probs[1]
    data['state3'] = list_probs[2]
    data['statement'] = None
    sentences = Sentence.query.filter_by(cat = cat).limit(100).all()
    texts = [np.random.choice(sentences).text for s in range(8)]
    data['statement'] = texts
    data['statement_real'] = None
    sentences_shelly = Sentence_Shelly.query.filter_by(cat = cat).limit(100).all()
    texts_org = [np.random.choice(sentences).text for s in range(8)]
    data['statement_real'] = texts_org
    data['reddit'] = ["some","fake", "reddit"]
    return jsonify(data)

@app.route("/form-data", methods=['GET','POST'])
def form_data():
    """
    Form templates
    """
    if request.method == 'POST':
        data = dict(request.form)
        d = FormData(data=data)
        db.session.add(d)
        db.session.commit()
        ## TODO actually saved
        return "data saved"
    else:
        return render_template('pre-show_web_form.html')

@app.route("/form-data/all", methods=['GET'])
def color_form_data():
    query = FormData.query.order_by(FormData.created_date.desc()).limit(10)
    data = [fd.data for fd in query]
    return jsonify(data)


@app.route("/submitted")
def thanks():
    """
    Thank you for completing form
    """
    return render_template('submitted.html')


if __name__ == '__main__':
    env = os.environ.get('ENV', 'dev')
    if env == 'prod':
        app.run(host='0.0.0.0')
    else:
        db.create_all()
        app.run(debug=True)


