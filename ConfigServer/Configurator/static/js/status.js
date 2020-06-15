
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
            let voltage = {
                'min': parseFloat(element.dataset.minVoltage),
                'max': parseFloat(element.dataset.maxVoltage),
                'current': parseFloat(item.value),
            }
            let barLength = (voltage.current - voltage.min) / (voltage.max - voltage.min);
            element.children[0].style.width = `${constrain(barLength * 100, 10, 100)}%`;
        }
        else {
            element.innerHTML = item.value;
        }
    }
}

const updateServer = new EventSource("update/");
updateServer.onmessage = function(event) {
    updateStatus(JSON.parse(event.data));
};
