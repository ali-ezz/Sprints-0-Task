// Task0 - Send Incident to Agent
// ServiceNow Business Rule.  Table: Incident [incident].  Advanced: true.
// When: after   |   Insert: checked   |   Update: UNCHECKED   (Update would loop on our write-back)
//
// This is the asset-pack script with two request headers added:
//   - X-Webhook-Secret            : must match WEBHOOK_SHARED_SECRET in the service .env
//   - ngrok-skip-browser-warning  : harmless; only relevant on an ngrok free tunnel
//
// Replace YOUR-TUNNEL-URL and YOUR_SHARED_SECRET before saving.

(function executeRule(current, previous /*null when async*/) {
    try {
        var payload = {
            "incident_sys_id": current.getValue('sys_id'),
            "number": current.getValue('number'),
            "short_description": current.getValue('short_description'),
            "description": current.getValue('description'),
            "priority": parseInt(current.getValue('priority'), 10)
        };

        var r = new sn_ws.RESTMessageV2();
        r.setEndpoint('https://YOUR-TUNNEL-URL/webhook');
        r.setHttpMethod('POST');
        r.setRequestHeader('Content-Type', 'application/json');
        r.setRequestHeader('X-Webhook-Secret', 'YOUR_SHARED_SECRET');
        r.setRequestHeader('ngrok-skip-browser-warning', 'true');
        r.setRequestBody(JSON.stringify(payload));
        r.executeAsync();

        gs.info('Task0: sent incident ' + current.getValue('number'));
    } catch (ex) {
        gs.error('Task0: failed to send incident: ' + ex.message);
    }
})(current, previous);
