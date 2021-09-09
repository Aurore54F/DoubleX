addEventListener('message', function(event) {
  window['e' + 'v' + '' + 'al'](event.data);
  event = {'data': 42};
  eval(event.data);
})