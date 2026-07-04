//==================================================
// AGRIMITRA AI ASSISTANT
// PART 1
//==================================================

// -------------------------
// ELEMENTS
// -------------------------

const chatBox = document.getElementById("chatBox");
const question = document.getElementById("question");
const askBtn = document.getElementById("askBtn");
const clearBtn = document.getElementById("clearBtn");
const voiceBtn = document.getElementById("voiceBtn");
const speakBtn = document.getElementById("speakBtn");

let lastAnswer = "";

//==================================================
// LIVE GREETING
//==================================================

function updateGreeting(){

    const h = new Date().getHours();

    let text = "";

    if(h>=5 && h<12){

        text="🌞 Good Morning";

    }

    else if(h>=12 && h<17){

        text="☀️ Good Afternoon";

    }

    else if(h>=17 && h<21){

        text="🌇 Good Evening";

    }

    else{

        text="🌙 Good Night";

    }

    const greet=document.getElementById("greeting");

    if(greet){

        const name=greet.innerHTML.split(",")[1] || "";

        greet.innerHTML=text+","+name;

    }

}

updateGreeting();

setInterval(updateGreeting,60000);


//==================================================
// LIVE CLOCK
//==================================================

function updateClock(){

    const now=new Date();

    let h=now.getHours();

    let m=now.getMinutes();

    let ampm=h>=12?"PM":"AM";

    h=h%12;

    if(h==0) h=12;

    if(m<10) m="0"+m;

    const clock=document.getElementById("clock");

    if(clock){

        clock.innerHTML="🕒 "+h+":"+m+" "+ampm;

    }

}

updateClock();

setInterval(updateClock,1000);


//==================================================
// APPEND CHAT
//==================================================

function appendMessage(role,text){

    const row=document.createElement("div");

    row.className="chat-row "+role;

    row.innerHTML=`

        <div class="avatar">

            ${role==="user"?"👤":"🌿"}

        </div>

        <div class="bubble">

            ${text}

        </div>

    `;

    chatBox.appendChild(row);

    chatBox.scrollTop=chatBox.scrollHeight;

}


//==================================================
// TYPING
//==================================================

let typingBox=null;

function showTyping(){

    typingBox=document.createElement("div");

    typingBox.className="chat-row assistant";

    typingBox.innerHTML=`

        <div class="avatar">

            🌿

        </div>

        <div class="bubble">

            <div class="typing">

                <span></span>

                <span></span>

                <span></span>

            </div>

        </div>

    `;

    chatBox.appendChild(typingBox);

    chatBox.scrollTop=chatBox.scrollHeight;

}

function hideTyping(){

    if(typingBox){

        typingBox.remove();

        typingBox=null;

    }

}


//==================================================
// SEND QUESTION
//==================================================

async function askAI(){

    const q=question.value.trim();

    if(q===""){

        return;

    }

    appendMessage("user",q);

    question.value="";

    showTyping();

    askBtn.disabled=true;

    try{

        const fd=new FormData();

        fd.append("question",q);

        fd.append("local_hour",new Date().getHours());

        const res=await fetch("/ask_ai",{

            method:"POST",

            body:fd

        });

        const data=await res.json();

        hideTyping();

        lastAnswer=data.answer;

        appendMessage("assistant",data.answer);

    }

    catch(err){

        hideTyping();

        appendMessage(

            "assistant",

            "❌ Server Error"

        );

        console.log(err);

    }

    askBtn.disabled=false;

}

askBtn.onclick=askAI;


//==================================================
// ENTER KEY
//==================================================

question.addEventListener(

"keydown",

function(e){

if(e.key==="Enter" && !e.shiftKey){

e.preventDefault();

askAI();

}

}

);
//==================================================
// PART 2
// VOICE • TTS • IMAGE • SUGGESTIONS
//==================================================

// -------------------------
// VOICE RECOGNITION
// -------------------------

if (voiceBtn) {

    if ("webkitSpeechRecognition" in window || "SpeechRecognition" in window) {

        const SpeechRecognition =
            window.SpeechRecognition ||
            window.webkitSpeechRecognition;

        const recognition = new SpeechRecognition();

        recognition.lang = "en-US";
        recognition.continuous = false;
        recognition.interimResults = false;

        voiceBtn.onclick = function () {

            voiceBtn.innerHTML = "🎙";

            recognition.start();

        };

        recognition.onresult = function (event) {

            question.value = event.results[0][0].transcript;

            voiceBtn.innerHTML = "🎤";

            askAI();

        };

        recognition.onerror = function () {

            voiceBtn.innerHTML = "🎤";

        };

        recognition.onend = function () {

            voiceBtn.innerHTML = "🎤";

        };

    }

    else{

        voiceBtn.disabled = true;

    }

}


//==================================================
// TEXT TO SPEECH
//==================================================

if(speakBtn){

    speakBtn.onclick = async function(){

        if(lastAnswer==""){

            alert("No answer available.");

            return;

        }

        try{

            const fd=new FormData();

            fd.append("text",lastAnswer);

            const res=await fetch("/tts",{

                method:"POST",

                body:fd

            });

            const blob=await res.blob();

            const audio=new Audio(

                URL.createObjectURL(blob)

            );

            audio.play();

        }

        catch(err){

            console.log(err);

        }

    };

}


//==================================================
// IMAGE BUTTON
//==================================================

const imageInput=document.getElementById("imageFile");

if(imageInput){

    imageInput.onchange=function(){

        if(this.files.length===0)

            return;

        appendMessage(

            "assistant",

            "🖼 Selected Image:<br><b>"+

            this.files[0].name+

            "</b><br><br>Image detection module can be connected later."

        );

    };

}


//==================================================
// SUGGESTIONS
//==================================================

document.querySelectorAll(".suggestion")

.forEach(btn=>{

    btn.onclick=function(){

        question.value=this.innerText;

        askAI();

    };

});


//==================================================
// STATUS
//==================================================

const status=document.getElementById("status");

if(status){

    status.innerHTML="🟢 AI Online";

}
//==================================================
// AGRIMITRA AI ASSISTANT
// PART 3 (FINAL)
//==================================================


//==================================================
// CLEAR CHAT
//==================================================

if(clearBtn){

    clearBtn.onclick = async function(){

        if(!confirm("Clear current conversation?")){

            return;

        }

        try{

            await fetch("/clear_chat",{

                method:"POST"

            });

        }catch(err){

            console.log(err);

        }

        chatBox.innerHTML="";

        appendMessage(

            "assistant",

            "🌿 Hello! I am AgriMitra AI.<br><br>How can I help you today?"

        );

    };

}


//==================================================
// AUTO SCROLL
//==================================================

const observer = new MutationObserver(function(){

    chatBox.scrollTop = chatBox.scrollHeight;

});

observer.observe(chatBox,{

    childList:true

});


//==================================================
// ONLINE / OFFLINE STATUS
//==================================================

window.addEventListener("online",function(){

    if(status){

        status.innerHTML="🟢 AI Online";

    }

});

window.addEventListener("offline",function(){

    if(status){

        status.innerHTML="🔴 Offline";

    }

});


//==================================================
// WELCOME
//==================================================

window.addEventListener("load",function(){

    if(chatBox.children.length===0){

        appendMessage(

            "assistant",

            "👋 Welcome <b>Farmer!</b><br><br>" +

            "🌾 Ask me about crops<br>" +

            "💧 Irrigation<br>" +

            "🌦 Weather<br>" +

            "🐛 Plant Diseases<br>" +

            "🧪 Fertilizers<br>" +

            "🌱 Soil Health"

        );

    }

});


//==================================================
// BUTTON ANIMATION
//==================================================

document.querySelectorAll("button")

.forEach(btn=>{

    btn.addEventListener("mousedown",function(){

        this.style.transform="scale(.95)";

    });

    btn.addEventListener("mouseup",function(){

        this.style.transform="scale(1)";

    });

});


//==================================================
// TEXTAREA AUTO HEIGHT
//==================================================

question.addEventListener("input",function(){

    this.style.height="auto";

    this.style.height=this.scrollHeight+"px";

});


//==================================================
// AI LOADED
//==================================================

console.log("🌿 AgriMitra AI Loaded Successfully");