import re, os
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_groq import ChatGroq
from langchain_core.output_parsers import JsonOutputParser
import json
class VideoResumeEvaluator2:
    def __init__(self, model_name="llama-3.3-70b-versatile"):
        """
        Initialize the evaluator with the specified LLM model and
        preserve the new functionality (cleaning + tone analysis).
        """
        api_key = os.getenv("GROQ_API_KEY")
        self.llm = ChatGroq(
            model=model_name, api_key = api_key
        )
        self.output_parser = JsonOutputParser()
        self.prompt_template = ChatPromptTemplate.from_messages([
            (
                "system", 
                "You are an expert interviewer. You are evaluating a video resume based on a given transcription.\n"
                "Give the detailed explanation of your response"
            ),
            (
                "user",
                """Transcription: {transcription_input}

You have to Evaluate Candiate's Performance based on two criteria's Qualitative Analysis and Quantitative Analysis 
you will be provided with the transcription of the candidate, 
Give at maximum 4 points in the Section of Qualitative Analysis make it clear and concise, necessarily make it in second person "you" in qualitative analysis, you have to talk about the Positives of the candidate
Give your answers in this format (e.g : You delivered the presentation with a clear voice and tone, Your articulation was up to the mark, Avoid using sentences like “Leading a team is just logistics”. This comes across as not being interested in
taking on leadership roles at all. Use word 'content' instead of 'transcription' in analysis.
, Overall a very confident presentation.) You can directly Point out the user, in whichever point you want. 
and in case of Quantitative Analysis, Give atleast 5 points, make it clear and concise, In Quantitative Analysis, talks about the Areas of Improvement, Talk About where user can improve, and give your output finally in dictionary format something like this. Also When Talking About Areas of Improvement, if there is a Rude Sentence, or a sentence that should not be said, point it in the Quantitative Analysis One, 
In a json file Key => Qualitative Analysis , Value = (your answer in points) Similarly, key = Quantitative Analysis , Value = (your answer in points) , , but ensure all the values which you are giving inside list should be in double quotes, Remember this very carefully, that should be in carefully, this is a strict requirement No extras, i only the dictionary Output, Remember this very Carefully, and also You are not allowed to talk about the feature, which you don't know, like you can't talk 
about his tone, posture, because you don't know about this, but you have the transcription, so try to give the points only on those basis ,  Refer the user as You, it should be like you are directly talking to him. 
"""
            )
        ])
        self.chain = self.prompt_template | self.llm | self.output_parser

    def clean_transcription(self, text: str) -> str:
        """
        Removes transcript timestamps like [0.00s - 9.00s] and extra spacing.
        """
        cleaned_text = re.sub(r'\[\d+\.\d+s\s*-\s*\d+\.\d+s\]', '', text)
        return ' '.join(cleaned_text.split())

    def map_expression_and_gesture_feedback(self, evaluation_scores):
        gesture_feedback_map = {
            "very high": "The speaker used excessive hand and body gestures. Reducing the intensity slightly could help avoid distraction and improve clarity.",
            "high": "The speaker used expressive gestures, though slightly overdone. A more measured use of gestures could enhance the overall delivery.",
            "medium": "The speaker maintained a good balance of hand and body gestures, effectively supporting their speech. Great job!",
            "low": "The speaker's gestures were minimal. Adding more expressive movements could make the presentation more engaging.",
            "very low": "The speaker rarely used any gestures. Incorporating some body language could significantly boost engagement.",
            "hands not detected": "Hands not detected. Please move further from the camera to allow for natural body movements to be captured."
        }

        expression_feedback_map = {
            5: "The speaker had excellent and very positive facial expressions. This greatly enhanced the delivery and helped connect with the audience.",
            4: "The speaker showed good facial expressions, adding warmth and engagement to the talk. A bit more consistency could make it even better.",
            3: "Facial expressions were moderate. While present at times, increasing expressiveness could make the talk more dynamic.",
            2: "There was limited facial expression, which may have made the delivery feel a bit flat. Try to show more enthusiasm or emotion when appropriate.",
            1: "Facial expressions were minimal or absent. Adding expressiveness can significantly improve the impact and connection with the audience.",
            0: "No expression data available."
        }

        gesture_comment = gesture_feedback_map.get(evaluation_scores.get("gesture_energy", "hands not detected"), "")
        expression_score = evaluation_scores.get("positive_expression_score", 0)
        expression_comment = expression_feedback_map.get(expression_score, "No expression data available.")

        return [expression_comment, gesture_comment]

    def evaluate_transcription(self, transcription_data, evaluation_scores=None):
        if isinstance(transcription_data, dict):
            text = transcription_data.get('text', '')
        else:
            text = transcription_data
        
        if not text.strip():
            raise ValueError("Transcription text must not be empty.")
        
        cleaned_text = self.clean_transcription(text)

       
        if evaluation_scores is None:
            try:
                with open("json/output.json", "r") as f:
                    evaluation_scores = json.load(f)
            except FileNotFoundError:
                evaluation_scores = {}

        llm_output = self.chain.invoke({
            "transcription_input": cleaned_text
        })

        if evaluation_scores:
            additional_feedback = self.map_expression_and_gesture_feedback(evaluation_scores)
            if isinstance(llm_output, dict) and "Quantitative Analysis" in llm_output:
                llm_output["Quantitative Analysis"].extend(additional_feedback)
        with open('json/quality_analysis.json' , 'w') as fp:
            json.dump(llm_output , fp)

        return llm_output
        