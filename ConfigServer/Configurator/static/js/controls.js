let items = document.getElementsByClassName('item');

function bind_slider_input(slider, input) {
    slider.numericInput = input;
    slider.addEventListener('input', function () {
        input.value = this.value;
    })
    input.addEventListener('input', function () {
        slider.value = this.value;
    })
}

function constrain_sliders_mutually(upper_slider, lower_slider) {
    upper_slider.addEventListener('input', function () {
        if (this.value < lower_slider.value) {
            lower_slider.value = this.value;
            lower_slider.numericInput.value = this.value;
        }
    })
    lower_slider.addEventListener('input', function () {
        if (this.value > upper_slider.value) {
            upper_slider.value = this.value;
            upper_slider.numericInput.value = this.value;
        }
    })
}

for (let item of items) {
    let slider = item.querySelector("input[type='range']");
    let input = item.querySelector("input[type='number']");
    if (slider && input) {
        bind_slider_input(slider, input);
    }
}

let shutdownVoltageSlider = document.getElementById('slider-shutdown-threshold'),
    recoveryVoltageSlider = document.getElementById('slider-recovery-threshold');
constrain_sliders_mutually(recoveryVoltageSlider, shutdownVoltageSlider)

let baseStationMode = document.getElementById('select-mode');
let svinModeSection = document.getElementById('group-svin-mode'),
    fixedModeSection = document.getElementById('group-fixed-mode');
baseStationMode.addEventListener('change', function () {
    if (this.value === 'disabled') {
        svinModeSection.classList.add('disabled');
        fixedModeSection.classList.add('disabled');
    } else if (this.value === 'svin') {
        svinModeSection.classList.remove('disabled');
        fixedModeSection.classList.add('disabled');
    } else if (this.value === 'fixed') {
        svinModeSection.classList.add('disabled');
        fixedModeSection.classList.remove('disabled');
    }
})
