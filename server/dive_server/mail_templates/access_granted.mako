
<%include file="_header.mako"/>

<div style="padding: 30px; font-family: helvetica, sans-serif;">
  <img
    width="200px"
    src="http://www.viametoolkit.org/wp-content/uploads/2016/08/viami_logo.png"
  >
  <h2>Access request granted</h2>
  <p>
    Your access request to ${dataset["meta"]["originalMediaName"]} has been approved by ${dataset_owner["login"]} in exchange of ${exchange_dataset["meta"]["originalMediaName"]}.
    You can see this new dataset in the Shared Data > Shared With Me tab.
  </p>
</div>

<%include file="_footer.mako"/>
