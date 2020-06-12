
function constrain(val, min, max) {
    return val > max ? max : val < min ? min : val;
}

function updateStatus(status) {
    for (let item of status) {
        let element = document.getElementById(item.name);

        if (item.name.endsWith('-status')) {
            element.innerHTML = item.value;
            element.classList.remove('badge-' + element.dataset.temper)
            element.dataset.temper = item.temper
            element.classList.add('badge-' + item.temper);
        }
        else if (item.name.endsWith('-bar')) {
            element.children[0].innerHTML = item.value;
            let anchorVoltage = parseFloat(element.dataset.voltage);
            let currentVoltage = parseFloat(item.value);
            let deviation = (currentVoltage - anchorVoltage) / (anchorVoltage / 3);
            element.children[0].style.width = `${constrain(50 + deviation * 100, 10, 100)}%`;
        }
        else {
            element.innerHTML = item.value;
        }
    }
}

const server = new EventSource("update/");
server.onmessage = function(event) {
    console.log(event.data);
    updateStatus(JSON.parse(event.data));
};
