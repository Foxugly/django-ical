/**
 * Bootstrap File Upload — vanilla JS rewrite.
 *
 * Original (Apache 2.0 / BSD 3-Clause):
 * Copyright (c) 2016 - 2018 David Stutz
 * https://github.com/davidstutz/bootstrap-file-upload
 *
 * Vanilla rewrite drops the jQuery dependency.
 */
(function (window) {
    'use strict';

    function FileUpload(element) {
        var defaultText = element.textContent;
        var input = element.querySelector('input[type="file"]');

        // Replace label text with a span; keep the input as a child.
        element.textContent = '';
        var span = document.createElement('span');
        span.className = 'file-upload-text';
        span.textContent = defaultText;
        element.appendChild(span);
        if (input) {
            element.appendChild(input);
            input.addEventListener('change', function () {
                if (input.value) {
                    var label = input.value.replace(/\\/g, '/').replace(/.*\//, '');
                    span.textContent = label;
                } else {
                    span.textContent = defaultText;
                }
            });
        }
    }

    window.FileUpload = FileUpload;
}(window));
