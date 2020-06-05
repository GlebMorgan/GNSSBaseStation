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

shutdown_voltage_slider = document.getElementById('slider-shutdown-threshold');
recovery_voltage_slider = document.getElementById('slider-recovery-threshold');
constrain_sliders_mutually(recovery_voltage_slider, shutdown_voltage_slider)
