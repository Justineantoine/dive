<script lang="ts">
import { defineComponent } from 'vue';
import { mapState } from 'vuex';
import DataShared from './DataShared.vue';
import DataDetails from './DataDetails.vue';
import { grantAccess, denyAccess } from '../api';

export default defineComponent({
  name: 'DataExchange',
  components: {
    DataShared,
    DataDetails,
  },
  props: {
    requestingUser: {
      type: String,
      required: true,
    },
    requestedDataset: {
      type: String,
      required: true,
    },
  },
  computed: {
    ...mapState('Location', ['selected', 'location']),
  },
  methods: {
    routeBackToRequests() {
      this.$router.push({
        name: 'requests',
      });
    },
    onAccept() {
      grantAccess(this.requestedDataset, this.requestingUser, this.selected[0]._id).then(() => {
        this.routeBackToRequests();
      });
    },
    onDeny() {
      denyAccess(this.requestedDataset, this.requestingUser).then(() => {
        this.routeBackToRequests();
      });
    },
  },
});
</script>

<template>
  <v-container
    fill-height
    :fluid="$vuetify.breakpoint.mdAndDown"
  >
    <v-row>
      <v-col cols="12">
        <DataShared
          :dataOwner="requestingUser"
          mode="exchange"
        />
      </v-col>
    </v-row>
    <v-row justify="end">
      <v-btn
        class="ml-2"
        color="primary"
        depressed
        :disabled="selected.length !== 1"
        @click="onAccept"
      >
        Accept request
      </v-btn>
      <v-btn
        class="ml-2"
        color="error"
        depressed
        @click="onDeny"
      >
        Deny Request
      </v-btn>
      <v-btn
        class="ml-2"
        depressed
        @click="routeBackToRequests"
      >
        Cancel
      </v-btn>
    </v-row>
  </v-container>
</template>
