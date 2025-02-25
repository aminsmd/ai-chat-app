# Highlevel architecture
<img src=pic/high_level.png>
<pre>
    1. save messages to the queue, and make sure the order of the messages are ascending based on the timestamp
    2. get one message from the queue
        select top-K messages based on the score (relevance + recency + importance)
        read the persona from variable role_description
        generate response from ChatGPT
    3. save the message to Chromadb
    4. save the response to Chromadb
</pre>


# Data Structures
## SQL database
There are 3 tables in msg_history.db
- history (deprecated)
    store previous histories
    colums:
    <pre>
        idx INTEGER PRIMARY KEY AUTOINCREMENT
        channel_name CHARACTER(20)
        user_id CHARACTER(20)
        ts TIMESTAMP
        role CHARACTER(20)
        content TEXT
        vector TEXT(empty)
    </pre>
- new_msg_queue
    store incoming messages, QPS > 1
    Current solution:
        currently we want to process the messages chronologically
    same colums as history
- persona
    store different personas
    colums:
    <pre>
    idx INTEGER PRIMARY KEY AUTOINCREMENT
    description TEXT NOT NULL
    active INTEGER
    used INTEGER
    </pre>
- file metadata
    <pre>
    file_id     CHARACTER(20) PRIMARY KEY
    channel     CHARACTER(20)
    user_id     CHARACTER(20)
    user_name   CHARACTER(32)
    title       CHARACTER(100)
    format      CHARACTER(20) // pdf, txt ...
    timestamp   TEXT
    path        CHARACTER(256)
    url         CHARACTER(256)
    </pre>
## Chroma DB
<pre>
{
    'ids': ['0'],
    'embeddings': ...,
    'documents': ['introduce highlights of One Piece'],
    'metadatas':
        [
            {
                'channel_name': 'channel_name',
                'user_id': 'user_id',
                'ts': 1693345341.745599,
                'role': 'user/assitance',
                'sum_imptce': 0,
                'importance': 0,
                'type': 'memory'/'reflection',
                'reasoning': '2,3,4' # only for reflection
            }
        ]
}

The user_id would be
    W1234567890 for teammates,
    'assistant' for replies from ChatGPT
</pre>

## Context for ChatGPT
<pre>
Example Context:
[
    {'role': 'system', 'content': 'You are a helpful assistant!'},
    {'role': 'assistant', 'content': 'Apologies for misunderstanding your request. Here are some other cities in California:\n\n1. Santa Barbara …..’},
    {'role': 'user', 'content': 'some cities in california', 'name': 'Janice_Gu'},
    {'role': 'user', 'content': 'ok, sounds great, tell me more about Napa briefly.', 'name': 'Janice_Gu'}
]

Reply:
    Napa is a city located in the heart of the Napa Valley, one of California's premier wine regions. It is known for its picturesque vineyards, world-class wineries, ... and golf courses. Napa truly offers a tranquil and indulgent escape for wine lovers and those seeking a relaxing vacation.
</pre>




# Code thoughts
- reply sequence [[1](#refer-anchor-1)]
In the document, we proposed several ways of sequence to reply to slack messages, we now use the third way, in the future, we may propose other way to implement
<br/><br/>

- score explanation
    score = recency + relevance + importance
    there two ways of importance, fixed and updated [[4](#refer-anchor-4)]
<br/><br/>
- Reflection

<pre>
    <code>
    if need_reflect:
        reflect
        reset_reflect_counter
    </code>
    1. Reflection Trigger
        message_count > 50
    2. Ways to store
        current only in memory <del>( maybe in the future memory + database)
        info_to_reflect <= say 50 messages
        save in memory, but if lost, reload from database</del>
    3. run_reflect
        a. generate focal points
            run prompt for info_to_reflect, get say 3 focal points
            example prompt:
            [{'role': 'user', 'name': 'Jing_Gu', 'content': 'top cities for view maples'},
            {'role': 'assistant', 'content': 'The top cities for viewing maple trees are:... so it\'s essential to check for the best time to visit these locations to catch the vibrant colors.'},
            ...
            , {'role': 'user',
                'content': 'Given only the information above, what are 3 most salient high-level questions we can answer about the subjects grounded in the statements?
                Output the response to the prompt above in json.\n
                Output must be a list of str.\n
                Example output json:\n
                {output:   ["What should Jane do for lunch", "Does Jane like strawberry", "Who is Jane"] }'}
            ]
            =>
            ['What are the top destinations for viewing maple trees?',
            'What are some popular spots for maple viewing in Tokyo?',
            'What are the best times to visit these locations for maple viewing?']

        b. retrieve memories for each focal point from all memories
            say return top n = 20
            focol point_1:
            [mem4, mem3, mem20,...,mem11] sorted by score
        c. generate insights for focal points
            [{'role': 'assistant', 'content': 'No 1. The top cities for viewing maple trees are:... vibrant colors.'},
            {'role': 'assistant', 'content': "No 0. Quebec City,... City."},
            ...
            {'role': 'user', 'content': 'What 5 high-level insights can you infer from the above conversation?Output the response to the prompt above in json.\nOutput must be a list of str.\n
            Example output json:\n
            {output:   ["The conversation seems to be casual and informal. (because of 1,4,6)",            "The participants are looking for birthday party locations. (because of 1,3)",            "There is confusion and uncertainty among the participants. (because of 3,5,7)",            "They are possibly navigating through a website or a list of options together. (because of 6),            "Indicating a preference for a particular location. (because of 5,9)"] }'}]

            =>
            {
                ...,
                'output': {
                    ['The conversation includes discussing top cities for viewing maple trees. (because of 1, 2)',
                    'The participants are seeking more information about maple viewing in Quebec City, Canada. (because of 3, 4)',
                    'There is an interest in comparing and determining the best city for viewing maple trees. (because of 4)',
                    'The participants are specifically interested in the top cities for viewing maple trees. (because of 1, 7)',
                    'The conversation involves sharing information and insights about maple viewing in different locations. (because of 2, 3)']}
            }

        d. add thoughts with importance to database
    4. reset reset_reflect_counter


</pre>

# Modules intro
- api_collection
including Sqlite3 and Chroma DB APIs
1. c_database_api and c_selection_api are for chroma db
    - responsible for retrieve topK histories based on score
    - calculate relevance, recency, importance
2. sq_database_api and sq_selection_api are for sqlite
    - responsible for the queue, which makes sure that we reply to messages chronologically
<br/><br/>





# Reference
<div id="refer-anchor-1"></div>
- [1] [reply sequence] https://docs.google.com/document/d/1JFDOTwiqjXGz0eNIn9i3JWOBJJWLA_-Q3njFbOr4Mz0/edit#bookmark=id.hzi37hdug9vq

<div id="refer-anchor-2"></div>
- [2] [flow_1] https://docs.google.com/document/d/1JFDOTwiqjXGz0eNIn9i3JWOBJJWLA_-Q3njFbOr4Mz0/edit#bookmark=id.i8hgmy7t36gl

<div id="refer-anchor-3"></div>
- [3] [flow_2] https://github.com/The-Language-and-Learning-Analytics-Lab/ChatGPT_Slack/blob/bot_score/Bolt/Graphs/code%20flow.png


<div id="refer-anchor-7"></div>
- [4] [importance] https://github.com/The-Language-and-Learning-Analytics-Lab/ChatGPT_Slack/blob/bot_score/Bolt/Graphs/importance.png
