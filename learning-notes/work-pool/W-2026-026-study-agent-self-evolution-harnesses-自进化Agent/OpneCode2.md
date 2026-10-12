# OpenCode 2.0

opencode 2.0 更新了， 支持了热更新热加载 

https://anoma.ly/notes/opencode-reloaded/

它最大的优势是：Agent 可以在同一个任务里，发现自身能力缺口、补上能力，然后立即继续解决问题。

是这样的

opencode 有个 execute 工具

这个 execute ， 提供了一个 js 的执行环境，其中暴露了一个 tools 对象
这个对象是一个map，key 是方法名， value是映射着 opencode 实现他的方法

比如 execute("return await tools.word_count({ text: "你好" });")

tools 对象就是在启动的时候，就包含在js运行环境内的
word_count是其中的一个方法，对应着某个js脚本

opencode 的 热更新，其实也就是在更新这个 tools 对象

可以理解为，多一个下面的这个对象
```js
{
  name: "word_count",
  description: "统计文本字数",
  input: { /* text 参数的格式 */ },
  execute: async ({ text }) => {
    // 实际统计逻辑
  }
}
```

新增完一个工具之后
会多这样一个声明

```
新增可用工具：
tools.word_count({ text: string })：统计文本字数。
请通过 execute 调用。
```