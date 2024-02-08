// messages.js
// Processes the messages from the host and updates any elements with
// "matching" id names (see below). Not written as a class because
// it is not likely that two instances are ever needed.
//
// Matching id names
// 
// mi_<measurement name>  --> update innerHTML using integer value
// ms_<mesurement name>   --> update innerHTML using string
// mf#_<measurement name> --> update innerHTML with # decimal places
//
// Examples
// mi_GpsDiffAge --> will get updated with status.GpsDiffAge
// ms_BaseStationId --> will display the BaseStationId
// mf3_Roll --> will get updates with nav.Roll
//
// This scheme only allows one HTML element per measurement.
// To display the same measurement twice on one web page
// perform a calculation to duplicate that measurement first.
//
// !!! Because this script adds global functions, watch out for any
// unintended clashes with scripts that you write !!!


// Global AmIdFilter is used to filter aruco marker ids so they can
// easily be seen (otherwise the last one sent is the only one
// you can read
AmIdFilter = -1 // Negative for no filter

// updateId is a useful function to update the innerHTML from
// the measurements from the websockets
// The element's id should be in the form mi_NcomName
// where NcomName is the key name
// For example mi_GpsTime would find "GpsTime" in meas and update
// the element with Id mi_GpsTime
// This is a way of shortening the code
// Note: using this scheme it is only possible to have one element
// updated using each key in meas.
function updateId(meas,id)
{
  let s = meas[id.substring(3)];
  if (s != undefined)
    document.getElementById(id).innerHTML = s;
}

// updateIdF is the same as updateId except it formats floating
// point numbers. The format is mf0_NcomName where "0" is the
// precision (0-9)
function updateIdF(meas,id)
{
  let precision = parseInt(id[2]);
  let s = meas[id.substring(4)];
  if (s != undefined)
    document.getElementById(id).innerHTML = s.toFixed(precision);      
}      

// doConnect...() is called to open a web socket
function doConnect()
{
  // The IP address is encoded in the query in the web address
  // If we don't request an IP address then we won't get any data
  // And, if there is no INS at that IP address then we also
  // won't get any data
  // Hopefully the query has been set correctly by page index.html
  const urlParams = new URLSearchParams(window.location.search);
  const ip = urlParams.get('ip');

  // Open the websocket
  websocket = new WebSocket(
    // Build the web socket address
    // Like ws://192.168.2.10:8000/nav,json?ip=192.168.2.62
    "ws://"
    + window.location.hostname
    + ":" + window.location.port
    + "/message.json?ip="
    + ip
  );
  // Set the callback functions for the websocket
  websocket.onopen = onOpen;
  websocket.onclose = onClose;
  websocket.onmessage = onMessage;
  websocket.onerror = onError;
}


// onOpen() is a callback when the websocket is opened
// We just set disconnected_... to false so we know that the
// websocket is open
function onOpen(evt)
{
  disconnected = false;
}

// onClose() is a callback when the websocket is closed
// for example if the network goes down, or the ncom-web stops
// We just set disconnected to true so we know that the
// websocket is closed (and then the timer will try to open it)
function onClose(evt)
{
  disconnected = true;
}
      
// onError() is a callback when the websocket has an error
// We just close it, set disconnected to true and then the
// timer will try and open another one
function onError(evt)
{
  websocket.close();
  disconnected = true;
}

// onMessage() is a callback when the websocket received a new message
// Process the message her
function onMessage(evt)
{
  message = JSON.parse(evt.data);

  // If onCalculations is defined then call it so that additional
  // measurements can be calculated. Useful for changing units,
  // or computing speed from velocity, etc.
  if( typeof onCalculations === 'function' )
    onCalculations(message);

  // A message can have more than one type in it
  // Currently all the onMessage_...() functions do the same thing
  // but there is scope for changes in the future
  if( 'nav' in message )    onMessage_nav(message.nav)
  if( 'status' in message ) onMessage_status(message.status)
  if( 'am' in message )     onMessage_am(message.am)
  if( 'connection' in message ) onMessage_connection(message.connection)

  // If onUpdate is defined then call it so that more advanced
  // elements can be updated. For example, innovation bars are not
  // updated using the scheme above
  if( typeof onUpdate === 'function' )
    onUpdate(message);

}

// onMessage_nav is called when a nav message is received on the
// websocket. All of the updating of the web page is done here
function onMessage_nav(nav)
{
  // Employ a cheat to make it easier to update the document
  // All elements with an id starting with "m_"
  // are assumed to be measurements in status
  // This for-loop updates them
  for( el of document.getElementsByTagName("*") )
  {
    if( /^m[is]_/.test(el.id) )
      updateId(nav,el.id);
    else if( /^mf[0-9]_/.test(el.id) )
      updateIdF(nav,el.id);
  }        
}
      
// onMessage_status is called when a status message is received on
// the websocket. All of the updating of the web page is done here
function onMessage_status(status)
{       
  // Employ a cheat to make it easier to update the document
  // All elements with an id starting with "m_"
  // are assumed to be measurements in status
  // This for-loop updates them
  for( el of document.getElementsByTagName("*") )
  {
    if( /^m[is]_/.test(el.id) )
      updateId(status,el.id);
    else if( /^mf[0-9]_/.test(el.id) )
      updateIdF(status,el.id);
  }
}
      
// onMessage_am is called when a new aruco marker measurement is received by
// the websocket. All of the updating of the web page is done here
function onMessage_am(am)
{       
  // Employ a cheat to make it easier to update the document
  // All elements with an id starting with "m_"
  // are assumed to be measurements in status
  // This for-loop updates them
  if ( AmIdFilter < 0 || AmIdFilter == am['AmId'] )
    for( el of document.getElementsByTagName("*") )
    {
      if( /^m[is]_/.test(el.id) )
        updateId(am,el.id);
      else if( /^mf[0-9]_/.test(el.id) )
        updateIdF(am,el.id);
    }        
} 

// onMessage_connection is called when a connection message is received
// on the websocket. All of the updating of the web page is done here.
function onMessage_connection(c)
{
  // Employ a cheat to make it easier to update the document
  // All elements with an id starting with "m_"
  // are assumed to be measurements in status
  // This for-loop updates them
  for( el of document.getElementsByTagName("*") )
  {
    if( /^m[is]_/.test(el.id) )
      updateId(c,el.id);
    else if( /^mf[0-9]_/.test(el.id) )
      updateIdF(c,el.id);
  }        
}



function message_init()
{
  // Connect to the websocket
  disconnected = true;
  doConnect();
}

window.addEventListener("load", message_init, false);


