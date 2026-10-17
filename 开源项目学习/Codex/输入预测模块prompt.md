# 原文
This is an app-generated request for a suggested next user message. The user did not write this message.

Your suggestion will appear in the user's empty message composer. They can accept it, edit it, or ignore it; it will not be sent automatically.

Predict the single message this user is most likely to type next from the visible conversation. Use the whole conversation to understand their current intent and the latest exchange. Choose the action and specific object that best continue that intent, rather than a generally useful follow-up. Express its core naturally in the user's voice, keeping the requirements needed to retain its meaning. Choose the strongest grounded move even if several continuations are possible; uncertainty about exact wording or incidental details is not a reason to return null. Use null only when the conversation offers no grounded next move at all.

Set suggestion to exactly one natural user message, one line, at most 240 characters, or null. No alternatives or explanation.

# 中文

这是一条由应用生成的请求，用于建议用户接下来可能发送的消息。这条请求不是用户本人写的。

你的建议会显示在用户当前为空的消息输入框中。用户可以接受、编辑或忽略它；它不会被自动发送。

根据当前可见的对话，预测这位用户接下来最可能输入的一条消息。结合整个会话，理解用户当前的意图以及最近一轮交流。选择最能延续这一意图的动作及其具体对象，而不是泛泛地推荐一个有用的后续问题或任务。用用户自己的口吻，自然地表达核心意思，同时保留准确传达其含义所必需的要求。即使存在多种可能的后续方向，也要选择其中最有依据的一步；仅仅无法确定具体措辞或次要细节，不构成返回 null 的理由。只有当对话完全无法支持任何有依据的下一步时，才使用 null。

将 suggestion 设置为恰好一条自然的用户消息，必须为单行，最多 240 个字符；或者设置为 null。不要提供备选项，也不要解释。

# 笔记

关键意思是：
- 预测“这个用户最可能说什么”，而非推荐一句泛泛有用的话。
- 结合整个会话的意图和最近一轮交流，选出具体动作、具体对象。
- 用用户自己的口吻，只给一条、单行、最多 240 个字符，不解释、不列备选。
- 只有没有任何有依据的下一步，才返回 null。