# AI ComputerCraft Control Idea

I want to have an AI control my computercraft computers (computers/turtles/pocket) and all of their perpherals.

## Requirements
- The webserver should be written with python3 you can choose the best mainstream modules to make that happen
- It should communicate over websocket and be able to interrupt any running program on the computercraft computers
- The error handling should all be passed back to python
- Ability to send custom user written lua scripts (saved on the web server)
- Ability to have wire in AI and have it generate and send lua scripts to the computer/turtle
  - I have github copilot so tell me how I can wire that in but future proof it so other AI Providers can be used in the future easily.
- Add in basic auth and oidc auth to the webserver since it might end up public facing
  - support multiple users with computers registering under a user
  - make nice ways for users to easily and fastly register computers
  - make it so computers can be shared

## References:
1. Semi working codebase in this project dont remember where I stopped at
  - I believe it was a web based program that could talk to computers in minecraft over websocket
  - ../../ccc
2. I have cctweaked version 1.120.0 installed in minecraft 26.1.2
  - my jar: cc-tweaked-26.1.2-forge-1.120.0.jar
  - github url: https://github.com/cc-tweaked/CC-Tweaked/tree/v26.1.2-1.120.0
3. Anything coordinate (location based) for turtles should idealy use my ../../squid/INS.lua library since it can handle using native gps with modems or user supplied position with internal tracking based on move functions.
4. This entire repo is filled with years of mine and my friends scripts so if needed reference any of them.
