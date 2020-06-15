function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        let cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            let cookie = cookies[i].trim();
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}


document.getElementById('button-uBlox-reset')
    .addEventListener('click', function () {
    if (confirm("uBlox module will be reset to default configuration.")) {
        resetUblox();
    }
})


function resetUblox() {
    let uBloxResetRequest = new XMLHttpRequest();
    uBloxResetRequest.onreadystatechange = function () {
        console.log(this)
        if (this.readyState === 4 && this.status === 200) {
            console.log('Received reply from server on reset uBlox: ' + this.responseText);
            handleReply(JSON.parse(this.responseText));
        }
    };
    let csrfToken = getCookie('csrftoken');
    let fd = new FormData();
    fd.append('query', 'uBlox reset');
    uBloxResetRequest.open("POST", "/uBlox-reset/", true);
    // uBloxResetRequest.setRequestHeader('Content-Type', 'application/json');
    uBloxResetRequest.setRequestHeader("X-CSRFToken", csrfToken);
    // uBloxResetRequest.send('uBlox reset');
    uBloxResetRequest.send(fd);
}


function handleReply(reply) {
    alert(reply.msg);
}
