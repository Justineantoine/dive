<script lang="ts">
import {
  defineComponent, ref, reactive, watch, computed, toRefs, onBeforeUnmount,
} from 'vue';
import type { DataOptions } from 'vuetify';
import { GirderModel, mixins } from '@girder/components/src';
import { useRouter } from 'vue-router/composables';
import { clientSettings } from 'dive-common/store/settings';
import { itemsPerPageOptions } from 'dive-common/constants';
import { useGirderRest } from '../plugins/girder';
import {
  getSharedWithMeFolders, getSharedFolders, requestAccess,
} from '../api';
import { DatasetAccessRequest, useStore } from '../store/types';
import eventBus from '../eventBus';

export default defineComponent({
  name: 'DataShared',
  props: {
    mode: {
      type: String,
      default: null,
    },
    dataOwner: {
      type: Array,
      default: [],
    },
  },
  setup(props) {
    const girderRest = useGirderRest();
    const requestStatusMap = ref<Record<string, boolean>>({});
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
    const filters = ref({
      owner: props.dataOwner,
    });

    const headers = [
      { text: 'File', value: 'name' },
      { text: 'Type', value: 'type' },
      { text: 'File Size', value: 'formattedSize' },
      { text: 'Shared By', value: 'ownerLogin' },
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
      const response = await (
        props.mode === 'shared-with-me'
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
        if (!!element?.access && !!girderRest.user) {
          requestStatusMap.value[element._id] = loadRequestStatus(element);
        }
      }));
    };

    function handleEvent() {
      updateOptions();
    }

    const onRowclick = (item: GirderModel) => {
      if (props.mode === 'shared-with-me') {
        router.push({
          name: 'home',
          params: {
            routeType: 'folder',
            routeId: item._id,
          },
        });
      } else {
        store.commit('Location/setSelected', [item]);
      }
    };

    function onRequest(item: GirderModel) {
      requestAccess(item._id).then(() => {
        eventBus.$emit('refresh-data-table');
      });
    }

    function loadRequestStatus(item: GirderModel) {
      return item.access.requests?.find(
        (u: DatasetAccessRequest) => (u.id === girderRest.user._id && u.status === 'pending'),
      );
    }

    function isAnnotationFolder(item: GirderModel) {
      return item._modelType === 'folder' && item.meta.annotate;
    }

    const availableOwners = computed(() => {
      const owners = dataList.value.map((item) => item.ownerLogin).filter(Boolean);
      return [...new Set(owners)].sort();
    });

    const filteredDataList = computed(() => (
      dataList.value.filter((item) => (
        !filters.value.owner.length || filters.value.owner.includes(item.ownerLogin)
      ))
    ));

    watch(tableOptions, updateOptions, {
      deep: true,
      immediate: true,
    });
    watch(() => clientSettings.rowsPerPage, updateOptions);
    watch(() => props.mode, updateOptions);

    store.commit('Location/setSelected', []);
    eventBus.$on('refresh-data-table', handleEvent);

    onBeforeUnmount(() => {
      eventBus.$off('refresh-data-table', handleEvent);
    });

    return {
      ...toRefs(tableOptions),
      availableOwners,
      clientSettings,
      filteredDataList,
      filters,
      getters,
      headers,
      isAnnotationFolder,
      itemsPerPageOptions,
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
  <div>
    <v-row
      class="ma-0"
      v-if="mode !== 'exchange'"
    >
      <v-col cols="12" sm="4">
        <v-autocomplete
          v-model="filters.owner"
          :items="availableOwners"
          label="Filter by owner"
          clearable
          multiple
          chips
        />
      </v-col>
    </v-row>
    <v-data-table
      v-model="locationStore.selected"
      :show-select="!getters['Location/locationIsViameFolder'] && mode === 'shared-with-me'"
      :headers="headers"
      :page.sync="page"
      :items-per-page.sync="clientSettings.rowsPerPage"
      :sort-by.sync="sortBy"
      :sort-desc.sync="sortDesc"
      :server-items-length="total"
      :items="filteredDataList"
      :footer-props="{ itemsPerPageOptions }"
      item-key="_id"
    >
      <!-- eslint-disable-next-line -->
      <template v-slot:item.name="{ item }">
        <div class="filename" @click="onRowclick(item)">
          <v-icon class="mb-1 mr-1">
            mdi-folder{{ item.public ? '' : '-key' }}
          </v-icon>
          {{ mode === 'shared-with-me' ? item.name : item.meta.originalMediaName }}
        </div>
      </template>
      <template #item.type="{ item }">
        {{ item.type }}
        <v-btn
          v-if="isAnnotationFolder(item) && mode === 'shared-with-me'"
          class="ml-2"
          x-small
          color="primary"
          depressed
          :to="{ name: 'viewer', params: { id: item._id } }"
        >
          Launch Annotator
        </v-btn>
        <v-btn
          v-else-if="isAnnotationFolder(item)"
          class="ml-2"
          x-small
          color="primary"
          depressed
          :to="{ name: 'previewer', params: { id: item._id } }"
        >
          Preview Data
        </v-btn>
        <v-btn
          v-if="isAnnotationFolder(item)
            && !mode
            && item._id in requestStatusMap
            && !requestStatusMap[item._id]"
          class="ml-2"
          x-small
          color="primary"
          depressed
          @click.stop="onRequest(item)"
        >
          Request Access
        </v-btn>
        <v-btn
          v-if="isAnnotationFolder(item) && !!requestStatusMap[item._id]"
          class="ml-2"
          x-small
          color="primary"
          depressed
          rounded
          outlined
          disabled
        >
          Access Requested
        </v-btn>
      </template>
      <template #no-data>
        <span class="pr-4">
          {{ mode === 'shared-with-me' ? 'No datasets have been shared with you yet.' : 'No shared dataset available for you' }}
        </span>
        <a href="https://kitware.github.io/dive/Web-Version/#sharing-data-with-teams">Learn more about sharing</a>
      </template>
    </v-data-table>
  </div>
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
