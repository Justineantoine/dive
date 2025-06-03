<script lang="ts">
import {
  defineComponent, ref, reactive, watch, toRefs, onBeforeUnmount,
} from 'vue';
import type { DataOptions } from 'vuetify';
import { mixins } from '@girder/components/src';
import { clientSettings } from 'dive-common/store/settings';
import { itemsPerPageOptions } from 'dive-common/constants';
import { grantAccess, getRequestedFolders } from '../api';
import { useStore, AccessRequest } from '../store/types';
import eventBus from '../eventBus';

export default defineComponent({
  name: 'DataSharedRequests',
  setup() {
    const total = ref();
    const requestList = ref([] as AccessRequest[]);
    const tableOptions = reactive({
      page: 1,
      sortBy: ['created'],
      sortDesc: [true],
    } as DataOptions);
    const store = useStore();
    const { getters } = store;
    const locationStore = store.state.Location;

    const headers = [
      { text: 'Dataset Name', value: 'name' },
      { text: 'Type', value: 'type' },
      { text: 'File Size', value: 'formattedSize' },
      { text: 'Requested By', value: 'requestingUser' },
    ];

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const fixSize: any = mixins.sizeFormatter.methods;

    const updateOptions = async () => {
      const {
        sortBy, page, sortDesc,
      } = tableOptions;
      const limit = clientSettings.rowsPerPage;
      const offset = (page - 1) * clientSettings.rowsPerPage;
      const sort = sortBy[0] || 'created';
      const sortDir = sortDesc[0] === false ? 1 : -1;
      const response = await getRequestedFolders(limit, offset, sort, sortDir);
      requestList.value = response.data;
      total.value = Number.parseInt(response.headers['girder-total-count'], 10);
      requestList.value.forEach((element) => {
        // eslint-disable-next-line no-param-reassign
        element.formattedSize = fixSize.formatSize(element.size);
        // eslint-disable-next-line no-param-reassign
        element.type = 'Dataset';
      });
    };

    function handleEvent() {
      updateOptions();
    }

    function onClick(item: AccessRequest, grant: boolean) {
      grantAccess(item._id, item.requestingUser._id, grant).then(() => {
        eventBus.$emit('refresh-request-table');
      });
    }

    watch(tableOptions, updateOptions, {
      deep: true,
      immediate: true,
    });
    watch(() => clientSettings.rowsPerPage, updateOptions);

    eventBus.$on('refresh-request-table', handleEvent);
    onBeforeUnmount(() => {
      eventBus.$off('refresh-request-table', handleEvent);
    });

    return {
      onClick,
      requestList,
      getters,
      updateOptions,
      total,
      locationStore,
      clientSettings,
      itemsPerPageOptions,
      ...toRefs(tableOptions),
      headers,
    };
  },
});

</script>

<template>
  <v-data-table
    :headers="headers"
    :page.sync="page"
    :items-per-page.sync="clientSettings.rowsPerPage"
    :sort-by.sync="sortBy"
    :sort-desc.sync="sortDesc"
    :server-items-length="total"
    :items="requestList"
    :footer-props="{ itemsPerPageOptions }"
    item-key="_id"
  >
    <!-- eslint-disable-next-line -->
    <template v-slot:item.name="{ item }">
      <div class="filename">
        <v-icon class="mb-1 mr-1">
          mdi-folder{{ item.public ? '' : '-key' }}
        </v-icon>
        {{ item.name }}
      </div>
    </template>
    <template #item.requestingUser="{ item }">
      {{ item.requestingUser.login }}
      <v-btn
        class="ml-2"
        x-small
        color="primary"
        depressed
        @click="onClick(item, true)"
      >
        Accept
      </v-btn>
      <v-btn
        class="ml-2"
        x-small
        color="error"
        depressed
        @click="onClick(item, false)"
      >
        Refuse
      </v-btn>
    </template>
    <template #no-data>
      <span class="pr-4">You have no pending requests.</span>
    </template>
  </v-data-table>
</template>

<style lang="scss" scoped>
.filename {
  cursor: pointer;
  opacity: 0.8;

  &:hover {
    opacity: 1;
  }
}
</style>
