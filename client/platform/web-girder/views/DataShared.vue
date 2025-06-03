<script lang="ts">
import {
  defineComponent, ref, reactive, watch, toRefs, onBeforeUnmount,
} from 'vue';
import type { DataOptions } from 'vuetify';
import { GirderModel, mixins } from '@girder/components/src';
import { useRouter } from 'vue-router/composables';
import { clientSettings } from 'dive-common/store/settings';
import { itemsPerPageOptions } from 'dive-common/constants';
import {
  getSharedWithMeFolders, getSharedFolders, requestAccess, hasRequested,
} from '../api';
import { DatasetAccessRequest, useStore } from '../store/types';
import eventBus from '../eventBus';

export default defineComponent({
  name: 'DataShared',
  props: {
    sharedWithMe: {
      type: Boolean,
      default: false,
    },
  },
  setup(props) {
    const loading = ref(true);
    const requestStatusMap = ref<Record<string, DatasetAccessRequest>>({});
    const router = useRouter();
    const total = ref();
    const dataList = ref([] as GirderModel[]);
    const tableOptions = reactive({
      page: 1,
      sortBy: ['created'],
      sortDesc: [true],
    } as DataOptions);
    const store = useStore();
    const { getters } = store;
    const locationStore = store.state.Location;

    const headers = [
      props.sharedWithMe
        ? { text: 'File', value: 'name' }
        : { text: 'Dataset', value: 'meta.originalDatasetName' },
      { text: 'Type', value: 'type' },
      { text: 'File Size', value: 'formattedSize' },
      { text: 'Shared By', value: 'ownerLogin' },
    ];

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const fixSize: any = mixins.sizeFormatter.methods;

    const updateOptions = async () => {
      loading.value = true;
      const {
        sortBy, page, sortDesc,
      } = tableOptions;
      const limit = clientSettings.rowsPerPage;
      const offset = (page - 1) * clientSettings.rowsPerPage;
      const sort = sortBy[0] || 'created';
      const sortDir = sortDesc[0] === false ? 1 : -1;
      const response = await (
        props.sharedWithMe
          ? getSharedWithMeFolders(limit, offset, sort, sortDir)
          : getSharedFolders(limit, offset, sort, sortDir)
      );
      dataList.value = response.data;
      total.value = Number.parseInt(response.headers['girder-total-count'], 10);
      await Promise.all(dataList.value.map(async (element) => {
        // eslint-disable-next-line no-param-reassign
        element.formattedSize = fixSize.formatSize(element.size);
        // eslint-disable-next-line no-param-reassign
        element.type = isAnnotationFolder(element) ? 'Dataset' : 'Folder';
        const result = await hasRequested(element._id);
        requestStatusMap.value[element._id] = result.data;
      }));
      loading.value = false;
    };

    function handleEvent() {
      updateOptions();
    }

    const onRowclick = (item: GirderModel) => {
      if (props.sharedWithMe) {
        router.push({
          name: 'home',
          params: {
            routeType: 'folder',
            routeId: item._id,
          },
        });
      }
    };

    function onRequest(item: GirderModel) {
      requestAccess(item._id).then(() => {
        eventBus.$emit('refresh-data-table');
      });
    }

    async function loadRequestStatus(item: GirderModel) {
      const result = await hasRequested(item._id);
      requestStatusMap.value[item._id] = result.data;
    }

    function isAnnotationFolder(item: GirderModel) {
      return item._modelType === 'folder' && item.meta.annotate;
    }

    watch(tableOptions, updateOptions, {
      deep: true,
      immediate: true,
    });
    watch(() => clientSettings.rowsPerPage, updateOptions);
    watch(() => props.sharedWithMe, updateOptions);

    eventBus.$on('refresh-data-table', handleEvent);
    onBeforeUnmount(() => {
      eventBus.$off('refresh-data-table', handleEvent);
    });

    return {
      ...toRefs(tableOptions),
      clientSettings,
      dataList,
      getters,
      headers,
      isAnnotationFolder,
      itemsPerPageOptions,
      loading,
      loadRequestStatus,
      locationStore,
      onRequest,
      onRowclick,
      requestStatusMap,
      total,
      updateOptions,
    };
  },
});

</script>

<template>
  <v-data-table
    v-model="locationStore.selected"
    :show-select="!getters['Location/locationIsViameFolder'] && sharedWithMe"
    :headers="headers"
    :page.sync="page"
    :items-per-page.sync="clientSettings.rowsPerPage"
    :sort-by.sync="sortBy"
    :sort-desc.sync="sortDesc"
    :server-items-length="total"
    :items="dataList"
    :footer-props="{ itemsPerPageOptions }"
    item-key="_id"
  >
    <!-- eslint-disable-next-line -->
    <template v-slot:item.name="{ item }">
      <div class="filename" @click="onRowclick(item)">
        <v-icon class="mb-1 mr-1">
          mdi-folder{{ item.public ? '' : '-key' }}
        </v-icon>
        {{ item.name }}
      </div>
    </template>
    <template #item.type="{ item }">
      {{ item.type }}
      <v-btn
        v-if="isAnnotationFolder(item) && sharedWithMe"
        class="ml-2"
        x-small
        color="primary"
        depressed
        :to="{ name: 'viewer', params: { id: item._id } }"
      >
        Launch Annotator
      </v-btn>
      <v-btn
        v-else-if="isAnnotationFolder(item) && !sharedWithMe"
        class="ml-2"
        x-small
        color="primary"
        depressed
        :to="{ name: 'previewer', params: { id: item._id } }"
      >
        Preview Data
      </v-btn>
      <v-btn
        v-if="isAnnotationFolder(item) && !sharedWithMe && !loading"
        class="ml-2"
        x-small
        color="primary"
        depressed
        :rounded="['pending', 'granted'].includes(requestStatusMap[item._id].status)"
        :outlined="['pending', 'granted'].includes(requestStatusMap[item._id].status)"
        :disabled="['pending', 'granted'].includes(requestStatusMap[item._id].status)"
        @click.stop="onRequest(item)"
      >
        {{ requestStatusMap[item._id].status === 'pending' ? 'Access Requested' : (requestStatusMap[item._id].status === 'granted' ? 'Access Granted' : 'Request Access') }}
      </v-btn>
    </template>
    <template #no-data>
      <span class="pr-4">No datasets have been shared with you yet.</span>
      <a href="https://kitware.github.io/dive/Web-Version/#sharing-data-with-teams">Learn more about sharing</a>
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
