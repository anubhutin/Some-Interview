from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_community.llms import Ollama
from langchain_groq import ChatGroq
import json
from audio_module.audio_analysis import analyze_audio_metrics
from config import audio_path, transcription_path 

  # Default to False if key not found
class VideoResumeEvaluator:
    def __init__(self, model_name="llama-3.3-70b-versatile"):
        self.llm = ChatGroq(model=model_name)
        self.output_parser = StrOutputParser()
        with open("json/presentation.json", "r") as file:  # Correct path
            data = json.load(file)

        presentation_mode = data.get("presentation_mode", False)
        if presentation_mode == "on":
            self.prompt_template = ChatPromptTemplate.from_messages([
                ("system", 
                "You are a communication coach reviewing a speech or talk using the transcript and audio metrics provided. Each sentence must explain the observation clearly. Back every observation with a reason. Do not summarize. Ensure the output is a sequence of meaningful, standalone sentences separated by full stops."),
                ("user", 
                """
    Transcription: {transcription_input}

    Questions:
    1. Did the Speaker Speak with Confidence? (One line answer)
    2. Did the speaker vary their tone, speed, and volume while delivering the speech/presentation? Here are the details provided about the tone, speed, pace, and volume, {audio_metrics}, I want you 
    to give the answer in a sentence format, (For ex : The Tone and Volume was appropriate. you could have maintained a steady Speed in Delivery. A few Words were pronounced very fast), I want you to give the answer in a proper sentence like the example, and doesn't provide the numerical metrics to user, it should be in sentence, but dont tell like, dont tell your that your tone was neutrl/sad/happy, say that your maintained a good tone, this is an example

    3. Did the speech have a structure of Opening, Body and Conclusion? (Give 2-3 line descriptive Explanation, no straight answers or marks should be provided, i want descriptive answers, this is mandatory  but seperated by full stops. Avoid conjunctions and commas)
    4. Was the overall “Objective” of the speech delivered clearly? (Give 2-3 line descriptive Explanation, no straight answers or marks should be provided, i want descriptive answers, this is mandatory  but seperated by full stops. Avoid conjunctions and commas)
    5. Was the content of the presentation/speech to the point, or did it include unnecessary details that may have distracted or confused the audience? (Give 2-3 line Explanation, no straight answers or marks should be provided, i want descriptive answers, this is mandatory)
   
    6. Was the content of the presentation/speech relevant to the objective of the presentation?  (3-4 lines Descriptive Answer  but seperated by full stops. Avoid conjunctions and commas)
    7. Was the content of the presentation/speech clear and easy to understand?  (2-3 lines explanation about hwo good or bad it was)
    8. Did the speaker keep the presentation engaging by adding relevant examples, anecdotes and data to back their content? (2-3 lines descriptive answer)
    9. Did the speaker demonstrate credibility? Will you trust the speaker?   (2-3 lines descriptive answer but seperated by full stops. Avoid conjunctions and commas)
    10. Did the speaker explain how the speech or topic of the presentation would benefit the audience and what they could gain from it?(2-3 lines descriptive answer but seperate it with full stops)
    11. Did the speaker make an emotional connection with the audience ? (2-3 lines descriptive answer  but seperated by full stops. Avoid conjunctions and commas)
    12. Overall, were you convinced/ persuaded with the speaker’s view on the topic? (2-3 lines descriptive answer but sepearate it with full stops and not commas, and no straight answers or marks should be provided, i want descriptive answers, this is mandatory)
    Only provide the answers to these questions—do not include any extra commentary. 
    Start your response with "These are the Answers:" and then list each answer on a new line. Refer the user as You, it should be like you are directly talking to him
                """
                )
            ])
        else:
            self.prompt_template = ChatPromptTemplate.from_messages([
                ("system", 
                "You are an expert interviewer evaluating a video resume based on a transcription and provided audio metrics. provide at least 3-4 sentences for each question. Please provide shorter multiple sentences without conjunctions and comma, instead use full stops. Use the following format for your answers"),
                ("user", 
                """
    Transcription: {transcription_input}

    Questions:
    1. Did the Speaker Speak with Confidence? (One line answer)
    2. Did the speaker vary their tone, speed, volume? Here are the details provided about the tone, speed, pace, and volume, {audio_metrics}, I want you 
    to give the answer in a sentence format, (For ex : The Tone and Volume was appropriate. you could have maintained a steady Speed in Delivery. A few Words were pronounced very fast), I want you to give the answer in a proper sentence like the example, and doesn't provide the numerical metrics to user, it should be in sentence, but dont tell like, dont tell your that your tone was neutrl/sad/happy, say that your maintained a good tone, this is an example
    3. Did they use any hand or body gesture while speaking? (One line answer)
    4. Did they have expression on thier face?  (One line answer)
    5. Who are you and what are your skills, expertise, personality traits ?
    6. Why are you the best person to fit this role?(Give 3 multiple line seperate answers, including the point, where he/she performed well/bad)
    7. How are you different from others?( 2-4 multiple lines but seperated by full stops. Avoid conjunctions and commas, including the point, where he/she performed well/bad)
    8. What value do you bring to the role? (2-4 multiple lines but seperated by full stops. Avoid conjunctions and commas, including the point, where he/she performed well/bad)
    9. Did the speech have a structure of Opening, Body and Conclusion? (Give a one line answer, including the point, where he/she performed well/bad)
    10. How was the quality of research for the topic? 
       Did the student’s speech demonstrate a good depth? 
       Did they cite the sources of research properly? 
        (Give 3 multiple line seperate answers, including the point, where he/she performed well/bad)
    11. How creatively did the student present the video? Give at max 3 multiple line seperate answers, including the point, where he/she performed well/bad)
    12. How convinced were you with the overall speech on the topic? 
        Was it persuasive? 
        Will you give them the job/opportunity? Give 3 multiple line seperate answers with full stop, including the point, where he/she performed well/bad)
    Only provide the answers to these questions—do not include any extra commentary. 2-4 multiple lines but seperated by full stops. Avoid conjunctions and commas
    Start your response with "These are the Answers:" and then list each answer on a new line. Refer the user as You, it should be like you are directly talking to him
                """
                )
            ])
        
        self.chain = self.prompt_template | self.llm | self.output_parser

    def evaluate_transcription(self, transcription, audio_metrics=""):
        transcription_input = transcription
        output = self.chain.invoke({
            'transcription_input': transcription_input, 
            'audio_metrics' : analyze_audio_metrics(audio_path , transcription_path)
        })
        return output