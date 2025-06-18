
<%include file="_header.mako"/>

<div style="padding: 30px; font-family: helvetica, sans-serif;">
  <img
    width="200px"
    src="http://www.viametoolkit.org/wp-content/uploads/2016/08/viami_logo.png"
  >
  <h2>Access request denied</h2>
  <p>
    Your request to access the dataset ${dataset["meta"]["originalMediaName"]} has been denied by ${dataset_owner["login"]}.
    Make sure you have shared some of your data so they can be exchanged.
  </p>
</div>

<%include file="_footer.mako"/>
