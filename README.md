# VeraGraph
Software for capturing, storing, and visualizing data from a Single-arm YuMi Collaborative Robot from ABB running a OmniCore controller.


## Method
The OmniCore controller is connected to the local network via the WAN port.
By using the ABB Rest-API, target values & states are subscribed to and a secure socket connection with the robot is established.

Updates of the subscribed states are sent to the computer in XML format where they get queried and the data points are extracted. 
Some further processing is done to extrapolate additional data points that are unavailable to request from the controller.

Once the data is retrieved and processed it's pushed to a Prometheus time series database running on the local machine on port 9090. 
The database is accessed by Grafana also running on the local machine on port 3000. Grafana further queries the data and finally displays it on a dashboard.
