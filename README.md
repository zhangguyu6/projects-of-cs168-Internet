# [berkeley cs168 projects](http://cs168.io/)
cs168计算机网络的课后项目
## project 1 : Chat Room
#### 简介
用python3.5实现的一个基于epoll的命令行多人聊天室  
#### 第三方依赖
无
#### 快速开始
启动服务器:`python3 server.py localhost 8989`  
启动客户端一:`python3 client.py localhost 8989`  
启动客户端二:`python3 client.py localhost 8989`  
客户端命令:
* /setname <name> 设置用户名 
* /create <channel> 创建频道'
* /join <channel> 加入频道'
* /ls 列出所有频道
* /exit 退出
* /help 帮助信息