
<%include file="_header.mako"/>

<div style="padding: 30px; font-family: helvetica, sans-serif;">
  <img
    width="200px"
    src="http://www.viametoolkit.org/wp-content/uploads/2016/08/viami_logo.png"
  >

  <h2>You have a pending access request</h2>

  <p>
    ${user["firstName"]} ${user["lastName"]} (${user["login"]}) has requested access to ${dataset["meta"]["originalDatasetName"]}.
  </p>

</div>

<%include file="_footer.mako"/>
